import asyncio
import threading
import platform
import subprocess
import re
from datetime import datetime
from icmplib import async_multiping, ping as sync_ping
from models import db, Node


class NetworkMonitor:
    def __init__(self, app=None):
        self.app = app
        self.is_running = False
        self._lock = threading.Lock()
        self._loop = None
        self._loop_thread = None
        self._use_system_ping = False

    def init_app(self, app):
        self.app = app
        self._start_event_loop()
        self._test_icmp_capability()

    def _test_icmp_capability(self):
        """Test if icmplib works, otherwise fallback to system ping."""
        try:
            result = sync_ping(
                '127.0.0.1',
                count=1,
                timeout=1,
                privileged=self.app.config.get('PING_PRIVILEGED', True)
            )
            if result.is_alive:
                print("[INIT] icmplib working in privileged mode")
                self._use_system_ping = False
                return
        except Exception as e:
            print(f"[INIT] icmplib privileged failed: {e}")

        try:
            result = sync_ping('127.0.0.1', count=1, timeout=1, privileged=False)
            if result.is_alive:
                print("[INIT] icmplib working in non-privileged mode")
                self.app.config['PING_PRIVILEGED'] = False
                self._use_system_ping = False
                return
        except Exception as e:
            print(f"[INIT] icmplib non-privileged failed: {e}")

        print("[INIT] Falling back to SYSTEM PING")
        self._use_system_ping = True

    def _start_event_loop(self):
        """Run a dedicated asyncio event loop in background thread."""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()

        import time
        while self._loop is None:
            time.sleep(0.05)

    def _system_ping(self, ip_address, count=2, timeout=1):
        """Fallback: Use system ping command."""
        system = platform.system().lower()
        try:
            if system == 'windows':
                cmd = ['ping', '-n', str(count), '-w', str(timeout * 1000), ip_address]
            else:
                cmd = ['ping', '-c', str(count), '-W', str(timeout), ip_address]

            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=(timeout * count) + 3
            )
            output = result.stdout

            packet_loss = 100.0
            response_time = 0.0

            if system == 'windows':
                loss_match = re.search(r'\((\d+)% loss\)', output)
                if loss_match:
                    packet_loss = float(loss_match.group(1))
                time_match = re.search(r'Average = (\d+)ms', output)
                if time_match:
                    response_time = float(time_match.group(1))
            else:
                loss_match = re.search(r'(\d+)% packet loss', output)
                if loss_match:
                    packet_loss = float(loss_match.group(1))
                time_match = re.search(r'rtt min/avg/max/mdev = [\d.]+/([\d.]+)/', output)
                if time_match:
                    response_time = float(time_match.group(1))

            is_alive = packet_loss < 100.0
            return {
                'address': ip_address,
                'is_alive': is_alive,
                'avg_rtt': response_time,
                'packet_loss': packet_loss / 100.0
            }
        except Exception as e:
            return {
                'address': ip_address,
                'is_alive': False,
                'avg_rtt': 0.0,
                'packet_loss': 1.0
            }

    def _evaluate_status(self, node, ping_success, packet_loss, response_time):
        """
        Simple SolarWinds-style: Only Up/Down with flap protection.
        No Warning state - prevents flapping completely.
        """
        config = self.app.config
        FAIL_THRESHOLD = config.get('FAIL_THRESHOLD', 3)
        SUCCESS_THRESHOLD = config.get('SUCCESS_THRESHOLD', 2)

        old_status = node.status
        new_status = old_status

        # Update counters
        if ping_success:
            node.consecutive_successes = (node.consecutive_successes or 0) + 1
            node.consecutive_failures = 0
        else:
            node.consecutive_failures = (node.consecutive_failures or 0) + 1
            node.consecutive_successes = 0

        # State machine - ONLY Up or Down
        if ping_success:
            if old_status == 'Node Down' or old_status == 'Unknown':
                if node.consecutive_successes >= SUCCESS_THRESHOLD:
                    new_status = 'Node Up'
            else:
                new_status = 'Node Up'
        else:
            if old_status == 'Node Up' or old_status == 'Unknown':
                if node.consecutive_failures >= FAIL_THRESHOLD:
                    new_status = 'Node Down'
            else:
                new_status = 'Node Down'

        # Update metrics (always)
        node.response_time = response_time
        node.packet_loss = packet_loss
        node.last_ping_success = ping_success
        node.last_checked = datetime.utcnow()

        # Apply status change
        if new_status != old_status:
            node.previous_status = old_status
            node.status = new_status
            node.last_status_change = datetime.utcnow()
            print(f"[STATUS CHANGE] {node.node_name} ({node.ip_address}): "
                  f"{old_status} -> {new_status}")

    def ping_single_node(self, node_id):
        """Manual ping for a single node."""
        with self.app.app_context():
            node = db.session.get(Node, node_id)
            if not node or not node.enabled:
                return

            try:
                if self._use_system_ping:
                    result = self._system_ping(
                        node.ip_address,
                        count=self.app.config.get('PING_COUNT', 2),
                        timeout=self.app.config.get('PING_TIMEOUT', 1)
                    )
                    response_time = round(result['avg_rtt'], 1)
                    packet_loss = round(result['packet_loss'] * 100, 1)
                    ping_success = result['is_alive']
                else:
                    result = sync_ping(
                        node.ip_address,
                        count=self.app.config.get('PING_COUNT', 2),
                        interval=0.2,
                        timeout=self.app.config.get('PING_TIMEOUT', 1),
                        privileged=self.app.config.get('PING_PRIVILEGED', True)
                    )
                    response_time = round(result.avg_rtt, 1) if result.is_alive else 0.0
                    packet_loss = round(result.packet_loss * 100, 1)
                    ping_success = result.is_alive

            except Exception as e:
                print(f"Ping error for {node.ip_address}: {e}")
                response_time = 0.0
                packet_loss = 100.0
                ping_success = False

            self._evaluate_status(node, ping_success, packet_loss, response_time)
            db.session.commit()

    def monitor_all_nodes(self):
        """Monitor all nodes."""
        with self._lock:
            if self.is_running:
                print("[MONITOR] Previous cycle still running, skipping...")
                return
            self.is_running = True

        start_time = datetime.utcnow()
        try:
            with self.app.app_context():
                nodes = Node.query.filter_by(enabled=True).all()
                if not nodes:
                    return

                ip_to_nodes = {}
                for node in nodes:
                    ip_to_nodes.setdefault(node.ip_address, []).append(node)

                ip_list = list(ip_to_nodes.keys())

                # Choose ping method
                if self._use_system_ping:
                    results = self._parallel_system_ping(ip_list)
                else:
                    future = asyncio.run_coroutine_threadsafe(
                        self._async_ping_all(ip_list),
                        self._loop
                    )
                    raw_results = future.result(timeout=120)
                    results = []
                    for r in raw_results:
                        results.append({
                            'address': r.address,
                            'is_alive': r.is_alive,
                            'avg_rtt': r.avg_rtt if r.is_alive else 0.0,
                            'packet_loss': r.packet_loss
                        })

                # Update nodes
                for result in results:
                    nodes_for_ip = ip_to_nodes.get(result['address'], [])
                    for node in nodes_for_ip:
                        ping_success = result['is_alive']
                        response_time = round(result['avg_rtt'], 1) if ping_success else 0.0
                        packet_loss = round(result['packet_loss'] * 100, 1)

                        self._evaluate_status(node, ping_success, packet_loss, response_time)

                db.session.commit()

                elapsed = (datetime.utcnow() - start_time).total_seconds()
                print(f"[MONITOR] Pinged {len(ip_list)} nodes in {elapsed:.1f}s")

        except Exception as e:
            print(f"[MONITOR ERROR] {e}")
            import traceback
            traceback.print_exc()
        finally:
            with self._lock:
                self.is_running = False

    def _parallel_system_ping(self, ip_list):
        """Parallel system ping using ThreadPoolExecutor."""
        from concurrent.futures import ThreadPoolExecutor
        max_workers = min(100, len(ip_list))
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ip = {
                executor.submit(
                    self._system_ping,
                    ip,
                    self.app.config.get('PING_COUNT', 2),
                    self.app.config.get('PING_TIMEOUT', 1)
                ): ip for ip in ip_list
            }
            for future in future_to_ip:
                try:
                    results.append(future.result(timeout=10))
                except Exception as e:
                    ip = future_to_ip[future]
                    results.append({
                        'address': ip,
                        'is_alive': False,
                        'avg_rtt': 0.0,
                        'packet_loss': 1.0
                    })
        return results

    async def _async_ping_all(self, ip_list):
        """Async ping all IPs concurrently."""
        try:
            results = await async_multiping(
                ip_list,
                count=self.app.config.get('PING_COUNT', 2),
                interval=0.2,
                timeout=self.app.config.get('PING_TIMEOUT', 1),
                concurrent_tasks=self.app.config.get('MAX_CONCURRENT_PINGS', 200),
                privileged=self.app.config.get('PING_PRIVILEGED', True)
            )
            return results
        except Exception as e:
            print(f"Async ping error: {e}")
            return []


monitor = NetworkMonitor()