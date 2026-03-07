from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_file
from librouteros import connect
from librouteros.query import Key
import psycopg2
import psycopg2.extras
import logging
import json
import os, sys
import time
from datetime import datetime
import paramiko
import ipaddress
import hmac
import hashlib

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key')

# --- CONFIG ---
# Docker Compose থেকে DATABASE_URL আসবে
DATABASE_URL = os.environ.get('DATABASE_URL')
WEBHOOK_SECRET = b'Wal@#2026ton' 
ALLOWED_IP = "54.235.3.84"
CORE_LICENSE_HASH = "446576656c6f7065642062792053686166666174204d61686d7564"

# --- CUSTOM DB WRAPPER (SQLite code কে Postgres এ চালানোর জন্য) ---
class DBConnection:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(DATABASE_URL)
            self.conn.autocommit = False # Transaction control
        except Exception as e:
            print(f"Database Connection Failed: {e}")
            self.conn = None

    def execute(self, query, params=None):
        if not self.conn: return None
        
        # SQLite এর '?' কে Postgres এর '%s' এ অটোমেটিক কনভার্ট করা হচ্ছে
        # যাতে আপনার নিচের শত শত লাইনের কোড এডিট করতে না হয়।
        fixed_query = query.replace('?', '%s')
        
        # Dictionary আকারে ডাটা পাওয়ার জন্য RealDictCursor
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(fixed_query, params)
            return cur
        except Exception as e:
            self.conn.rollback()
            raise e

    def commit(self):
        if self.conn: self.conn.commit()

    def close(self):
        if self.conn: self.conn.close()
    
    # fetchone/fetchall সাপোর্ট করার জন্য
    def fetchall(self):
        # এটি ডাইরেক্ট কল হবে না, cursor থেকে হবে, কিন্তু সেইফটি মেথড
        pass 

# --- DATABASE SETUP ---
def get_db_connection():
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL missing!")
        return None
    return DBConnection()

def init_db():
    conn = get_db_connection()
    if not conn: return
    
    # Postgres Syntax: SERIAL PRIMARY KEY ব্যবহার হয়েছে
    conn.execute('''
        CREATE TABLE IF NOT EXISTS routers (
            id SERIAL PRIMARY KEY,
            router_name TEXT,
            ip_address TEXT,
            username TEXT,
            password TEXT,
            api_port INTEGER DEFAULT 9999,
            ssh_port INTEGER DEFAULT 999, 
            room_prefix TEXT UNIQUE
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS guest_logs (
            id SERIAL PRIMARY KEY,
            guest_name TEXT,
            phone TEXT,
            email TEXT,
            room_no TEXT,
            router_ip TEXT,
            event_type TEXT,
            checkin_date TEXT,
            checkout_date TEXT,
            full_payload TEXT, 
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("PostgreSQL Database Initialized.")

# অ্যাপ রান হওয়ার সময় টেবিল চেক করবে
try:
    init_db()
except Exception as e:
    print(f"DB Init Warning: {e}")

# --- SGNATURE SHA256 --- #
def verify_signature(payload, received_signature):
    if not received_signature:
        return False
    computed_signature = hmac.new(WEBHOOK_SECRET, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed_signature, received_signature)

# --- HELPER: MIKROTIK ACTION ---
def manage_hotspot_user(router_info, action, phone, room_no, guest_name, departure_date):
    try:
        api = connect(
            host=router_info['ip_address'],
            username=router_info['username'],
            password=router_info['password'],
            port=router_info['api_port'],
            timeout=10
        )
        
        user_path = api.path('ip', 'hotspot', 'user')
        
        existing = list(user_path.select(Key('name') == room_no))
        
        if action == 'remove':
            if existing:
                user_path.remove(existing[0]['.id'])
                api.close()
                return True, f"User {room_no} removed (Void/Delete)."
            else:
                api.close()
                return True, "User not found, nothing to remove."

        comment_text = f"Guest: {guest_name} | Phone: {phone} | Out: {departure_date}"
        
        if existing:
            user_path.update(
                **{'.id': existing[0]['.id'], 
                   'password': phone, 
                   'comment': comment_text}
            )
            msg = "User Updated"
        else:
            user_path.add(
                name=room_no,
                password=phone,
                comment=comment_text,
                profile="default"
            )
            msg = "User Created"
            
        api.close()
        return True, msg

    except Exception as e:
        print(f"Mikrotik Error: {e}")
        return False, str(e)


################## WEBHOOK ################################
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    received_sig = request.headers.get('X-Signature-SHA256')
    if not verify_signature(request.data, received_sig):
        return jsonify({"status": "forbidden", "message": "Invalid Signature"}), 403
    data = request.json
    event = data.get('event')
    room_no = str(data.get('roomNumber', ''))
    is_void = str(data.get('isVoid', '0'))
    guest_info = data.get('Guest Information', {})
    phone = data.get('phoneNumber') or guest_info.get('phoneNumber', '')
    email = data.get('emailAddress') or guest_info.get('emailAddress', '')
    first_name = data.get('firstName') or guest_info.get('firstName', '')
    last_name = data.get('lastName') or guest_info.get('lastName', '')
    guest_name = f"{first_name} {last_name}".strip()
    checkin_info = data.get('Check-In Information', {})
    checkin_date = data.get('checkInDate_ISO') or checkin_info.get('checkInDate_ISO', '')
    departure_date = data.get('departureDate_ISO', '').split('T')[0] # YYYY-MM-DD
    room_prefix = room_no[0] if room_no else ""
    full_payload_str = json.dumps(data)

    conn = get_db_connection()
    
    try:
        router = conn.execute("SELECT * FROM routers WHERE room_prefix = ?", (room_prefix,)).fetchone()
        router_ip_log = router['ip_address'] if router else "No Match"
        
        conn.execute("""
            INSERT INTO guest_logs 
            (guest_name, phone, email, room_no, router_ip, event_type, checkin_date, checkout_date, full_payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (guest_name, phone, email, room_no, router_ip_log, f"{event} (Void:{is_void})", checkin_date, departure_date, full_payload_str))
        conn.commit()

        if not router:
            return jsonify({"status": "ignored", "message": f"No router mapped for prefix {room_prefix}"}), 200
        if is_void == '1' or event in ['Delete', 'BadVisitor_Add']:
            success, msg = manage_hotspot_user(router, 'remove', phone, room_no, guest_name, departure_date)
            
        elif event in ["CheckIn", "CheckInAndWriteInPMS", "Update", "UpdateAndWriteInPMS"]:
            success, msg = manage_hotspot_user(router, 'add', phone, room_no, guest_name, departure_date)
            
        else:
            success, msg = True, "Event ignored (Action not required)"

        if success:
            return jsonify({"status": "success", "message": msg}), 200
        else:
            return jsonify({"status": "error", "message": msg}), 500

    except Exception as e:
        print(f"Webhook Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()
    
    return jsonify({"status": "success"}), 200



######## API Helper ############
def connect_to_mikrotik():
    if 'target_ip' not in session:
        return None
    try:
        return connect(
            host=session['target_ip'], 
            username=session['target_user'], 
            password=session['target_pass'],
            port=session.get('target_port', 9999),
            timeout=10
        )
    except Exception as e:
        print(f"Connection Error: {e}")
        return None

#################### HOME PAGE ###########################
@app.route('/')
def home():
    conn = get_db_connection()
    routers = conn.execute("SELECT * FROM routers").fetchall()
    conn.close()
    return render_template('home.html', routers=routers)

################# ROUTER MANAGEMENT #######################
@app.route('/add-router', methods=['POST'])
def add_router():
    name = request.form.get('name')
    ip = request.form.get('ip')
    user = request.form.get('username')
    password = request.form.get('password')
    prefix = request.form.get('room_prefix')
    api_port = request.form.get('api_port') or 9999
    ssh_port = request.form.get('ssh_port') or 999

    if name and ip:
        try:
            conn = get_db_connection()
            conn.execute("""
                INSERT INTO routers (router_name, ip_address, username, password, room_prefix, api_port, ssh_port) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, ip, user, password, prefix, api_port, ssh_port))
            conn.commit()
            conn.close()
            flash("Router Added Successfully!", "success")
        except psycopg2.IntegrityError:
            flash("Error: Room Prefix must be unique!", "danger")
        except Exception as e:
            flash(f"Database Error: {e}", "danger")
            
    return redirect(url_for('home'))

@app.route('/edit-router/<int:id>', methods=['POST'])
def edit_router(id):
    name = request.form.get('name')
    ip = request.form.get('ip')
    user = request.form.get('username')
    password = request.form.get('password')
    prefix = request.form.get('room_prefix')
    api_port = request.form.get('api_port') or 9999
    ssh_port = request.form.get('ssh_port') or 999
    
    if name and ip:
        conn = get_db_connection()
        conn.execute("""
            UPDATE routers 
            SET router_name=?, ip_address=?, username=?, password=?, room_prefix=?, api_port=?, ssh_port=?
            WHERE id=?
        """, (name, ip, user, password, prefix, api_port, ssh_port, id))
        conn.commit()
        conn.close()
        flash("Router Updated Successfully!", "info")
    return redirect(url_for('home'))

@app.route('/delete-router/<int:id>')
def delete_router(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM routers WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Router Deleted!", "warning")
    return redirect(url_for('home'))

################# AUTHENTICATION #######################
@app.route('/configure/mikrotik')
def mikrotik_auth_page():
    r_id = request.args.get('id')
    target_ip = ""
    target_user = ""
    target_pass = ""
    if r_id:
        conn = get_db_connection()
        router = conn.execute("SELECT * FROM routers WHERE id=?", (r_id,)).fetchone()
        conn.close()
        if router:
            target_ip = router['ip_address']
            target_user = router['username']
            target_pass = router['password']
    return render_template('router_auth.html', target_ip=target_ip, user=target_user, password=target_pass)

@app.route('/mikrotik/authenticate', methods=['POST'])
def mikrotik_authenticate():
    session['target_ip'] = request.form['router_ip']
    session['target_user'] = request.form['router_user']
    session['target_pass'] = request.form['router_pass']
    conn = get_db_connection()
    router = conn.execute("SELECT api_port, ssh_port FROM routers WHERE ip_address=?", (session['target_ip'],)).fetchone()
    conn.close()
    if router:
        session['target_port'] = router['api_port']
        session['target_ssh_port'] = router['ssh_port']
    else:
        session['target_port'] = 9999
        session['target_ssh_port'] = 999
    try:
        api = connect(
            host=session['target_ip'], 
            username=session['target_user'], 
            password=session['target_pass'], 
            port=session['target_port'], 
            timeout=5
        )
        api.close()
        return redirect(url_for('mikrotik_gui_main'))
    except Exception as e:
        flash(f"Authentication Failed: {str(e)}", "danger")
        return redirect(url_for('mikrotik_auth_page', ip=session['target_ip']))


################# LOGS #######################
@app.route('/logs')
def view_logs():
    conn = get_db_connection()
    logs = conn.execute('SELECT * FROM guest_logs ORDER BY id DESC LIMIT 100').fetchall()
    conn.close()
    return render_template('db_logs.html', logs=logs)




# --- MIKROTIK DASHBOARD & FEATURES ---
@app.route('/mikrotik/gui-main')
def mikrotik_gui_main():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))
        resource = list(api.path('/system/resource').select())[0]
        interfaces = list(api.path('/interface').select())
        addresses = list(api.path('/ip/address').select())
        return render_template('mikrotik_dashboard.html', res=resource, interfaces=interfaces, ip_addresses=addresses)
    except:
        return redirect(url_for('logout'))
################# mikrotik ip list #################

@app.route('/mikrotik/ip-list')
def ip_list_page():
    if 'target_ip' not in session: return redirect('/')
    api = connect_to_mikrotik() 
    addresses = list(api.path('ip', 'address').select())
    interfaces = list(api.path('interface').select())
    return render_template('mikrotik_ip_addresses.html', ip_addresses=addresses, interfaces=interfaces)

################# ip add #################
@app.route('/mikrotik/add-ip', methods=['POST'])
def add_ip_logic():
    if 'target_ip' not in session: return redirect('/')
    
    new_ip = request.form.get('address')
    target_interface = request.form.get('interface')

    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))

        api.path('ip', 'address').add(address=new_ip, interface=target_interface)
        return redirect(url_for('ip_list_page'))
    except Exception as e:
        return f"Error adding IP: {str(e)}"

################### ip enable/disable#####################

@app.route('/mikrotik/toggle-ip', methods=['POST'])
def toggle_ip():
    if 'target_ip' not in session: return redirect('/')
    
    ip_id = request.form.get('ip_id')
    current_status = request.form.get('current_status')
    new_disabled_state = False if (current_status.lower() == 'true' or current_status == 'yes') else True
    
    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))
        
        api.path('ip', 'address').update(**{
            '.id': ip_id, 
            'disabled': new_disabled_state
        })
        
        return redirect(url_for('ip_list_page'))
    except Exception as e:
        return f"Error updating IP: {str(e)} <br><a href='/mikrotik/ip-list'>Go Back</a>"

################ mikrotik ip delete###########################
@app.route('/mikrotik/delete-ip', methods=['POST'])
def delete_ip():
    if 'target_ip' not in session: return redirect('/')
    ip_id = request.form.get('ip_id')
    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))   
        api.path('ip', 'address').remove(ip_id)
        return redirect(url_for('ip_list_page'))
    except Exception as e:
        return f"Error: {str(e)}"

########################ip adress Edit#########################
@app.route('/mikrotik/edit-ip', methods=['POST'])
def edit_ip():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        ip_id = request.form['ip_id']
        new_address = request.form['address']
        new_interface = request.form['interface']
        api.path('/ip/address').update(**{
            '.id': ip_id,
            'address': new_address,
            'interface': new_interface
        })

        return redirect(url_for('ip_list_page')) 
    except Exception as e:
        return f"Update Error: {str(e)}"


################ mikrotik interface ###########################

@app.route('/mikrotik/interfaces')
def list_interfaces():
    if 'target_ip' not in session: return redirect(url_for('mikrotik_auth_page'))
    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))   
        interface_list = list(api.path('/interface').select())

        def convert_to_human(bytes_val):
            try:
                bytes_val = int(bytes_val)
                if bytes_val < 1024 * 1024: return f"{round(bytes_val/1024, 2)} KB"
                elif bytes_val < 1024 * 1024 * 1024: return f"{round(bytes_val/(1024*1024), 2)} MB"
                else: return f"{round(bytes_val/(1024*1024*1024), 2)} GB"
            except: return "0 B"

        for iface in interface_list:
            rx = iface.get('rx-byte') or iface.get('rx-bytes') or 0
            tx = iface.get('tx-byte') or iface.get('tx-bytes') or 0
            iface['mac_address'] = iface.get('mac-address', 'N/A')
            iface['rx_total'] = convert_to_human(rx)
            iface['tx_total'] = convert_to_human(tx)
            iface['is_disabled'] = str(iface.get('disabled', 'false')).lower()

        return render_template('mikrotik_interfaces.html', interfaces=interface_list)
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/mikrotik/interface-traffic/<name>')
def get_traffic_data(name):
    if 'target_ip' not in session: return jsonify({"tx": "0 bps", "rx": "0 bps"}), 401
    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))   
        traffic = api.path('/interface/monitor-interface')(interface=name, once=True)
        
        if traffic:
            tx_bps = traffic[0].get('tx-bits-per-second') or traffic[0].get('tx_bits_per_second') or 0
            rx_bps = traffic[0].get('rx-bits-per-second') or traffic[0].get('rx_bits_per_second') or 0
        else: tx_bps, rx_bps = 0, 0

        def format_speed(bps):
            bps = int(bps)
            if bps < 1000: return f"{bps} bps"
            elif bps < 1000000: return f"{round(bps/1000, 1)} Kbps"
            else: return f"{round(bps/1000000, 2)} Mbps"

        return jsonify({"tx": format_speed(tx_bps), "rx": format_speed(rx_bps)})
    except:
        return jsonify({"tx": "0 bps", "rx": "0 bps"})

@app.route('/mikrotik/interface/disable/<name>')
def disable_interface(name):
    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))   
        api.path('/interface').update(**{'.id': name, 'disabled': 'yes'})
        return redirect(url_for('list_interfaces'))
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/mikrotik/interface/enable/<name>')
def enable_interface(name):
    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))   
        api.path('/interface').update(**{'.id': name, 'disabled': 'no'})
        return redirect(url_for('list_interfaces'))
    except Exception as e:
        return f"Error: {str(e)}"





################# MIKROTIK IP SERVICES (IP -> Services) #################

# 1. View Services List
@app.route('/mikrotik/system/services')
def list_system_services():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        if not api: return redirect(url_for('logout'))
        
        # Get all services
        services = list(api.path('/ip/service').select())
        
        # Sort by name for clean view
        services = sorted(services, key=lambda k: k.get('name', ''))
        
        return render_template('mikrotik_services.html', services=services)
    except Exception as e:
        flash(f"Error loading services: {str(e)}", "danger")
        return redirect(url_for('mikrotik_gui_main'))

# 2. Edit Service (Port & Available IP)
@app.route('/mikrotik/system/services/edit', methods=['POST'])
def edit_system_service():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        
        service_id = request.form.get('service_id')
        new_port = request.form.get('port')
        address = request.form.get('address') 
        data = {'.id': service_id, 'port': int(new_port)}
        if address and address.strip():
            data['address'] = address
        else:
            data['address'] = "" 

        api.path('/ip/service').update(**data)
        
        flash("Service updated successfully!", "success")
    except Exception as e:
        flash(f"Update Failed: {str(e)}", "danger")
        
    return redirect(url_for('list_system_services'))

# 3. Enable/Disable Service (Toggle)
@app.route('/mikrotik/system/services/toggle/<id>/<action>')
def toggle_system_service(id, action):
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        
        # Action determines disabled state
        is_disabled = 'yes' if action == 'disable' else 'no'
        
        api.path('/ip/service').update(**{
            '.id': id,
            'disabled': is_disabled
        })
        
        msg = "Service Disabled!" if action == 'disable' else "Service Enabled!"
        flash(msg, "info")
    except Exception as e:
        flash(f"Action Failed: {str(e)}", "danger")
        
    return redirect(url_for('list_system_services'))

@app.route('/mikrotik/system/services/delete/<id>')
def delete_system_service(id):
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        api.path('/ip/service').remove(id)
        flash("Service deleted successfully!", "warning")
    except Exception as e:
        flash(f"Delete Failed (System services cannot usually be deleted): {str(e)}", "danger")
        
    return redirect(url_for('list_system_services'))



################# MIKROTIK BRIDGE MANAGER (FIXED) #################

# 1. VIEW ALL (Bridges, Ports, VLANs)
@app.route('/mikrotik/bridge')
def list_bridges():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        
        # 1. Bridges
        bridges = list(api.path('/interface/bridge').select())
        for b in bridges:
            raw_vf = b.get('vlan-filtering')
            if str(raw_vf).lower() in ['true', 'yes', '1', 'on']:
                b['vlan_filtering'] = 'yes'
            else:
                b['vlan_filtering'] = 'no'
            
            raw_disabled = b.get('disabled')
            b['is_disabled'] = str(raw_disabled).lower() in ['true', 'yes', '1']

        bridge_ports = list(api.path('/interface/bridge/port').select())
        bridge_vlans = list(api.path('/interface/bridge/vlan').select())
        interfaces = list(api.path('/interface').select())

        return render_template('mikrotik_bridge.html', 
                               bridges=bridges, 
                               bridge_ports=bridge_ports,
                               bridge_vlans=bridge_vlans, 
                               interfaces=interfaces)
    except Exception as e:
        flash(f"Data Load Error: {str(e)}", "danger")
        return redirect(url_for('mikrotik_gui_main'))

# --- BRIDGE OPERATIONS ---
@app.route('/mikrotik/bridge/add', methods=['POST'])
def add_bridge():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        vf = 'yes' if request.form.get('vlan_filtering') else 'no'
        
        api.path('/interface/bridge').add(
            name=request.form.get('name'),
            arp=request.form.get('arp', 'enabled'),
            **{'vlan-filtering': vf},
            comment=request.form.get('comment')
        )
        flash("Bridge added successfully!", "success")
    except Exception as e:
        flash(f"Bridge Add Failed: {str(e)}", "danger")
    return redirect(url_for('list_bridges', tab='bridge'))

@app.route('/mikrotik/bridge/edit', methods=['POST'])
def edit_bridge():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        vf = 'yes' if request.form.get('vlan_filtering') else 'no'
        
        api.path('/interface/bridge').update(**{
            '.id': request.form.get('bridge_id'),
            'name': request.form.get('name'),
            'arp': request.form.get('arp'),
            'vlan-filtering': vf,
            'comment': request.form.get('comment')
        })
        flash("Bridge updated!", "success")
    except Exception as e:
        flash(f"Update Failed: {str(e)}", "danger")
    return redirect(url_for('list_bridges', tab='bridge'))

@app.route('/mikrotik/bridge/delete/<id>')
def delete_bridge(id):
    try:
        api = connect_to_mikrotik()
        api.path('/interface/bridge').remove(id)
        flash("Bridge deleted!", "warning")
    except Exception as e:
        flash(f"Delete Error: {str(e)}", "danger")
    return redirect(url_for('list_bridges', tab='bridge'))

@app.route('/mikrotik/bridge/toggle/<id>/<action>')
def toggle_bridge(id, action):
    try:
        api = connect_to_mikrotik()
        state = 'yes' if action == 'disable' else 'no'
        api.path('/interface/bridge').update(**{'.id': id, 'disabled': state})
        flash(f"Bridge {action}d!", "success")
    except Exception as e:
        flash(f"Action Error: {str(e)}", "danger")
    return redirect(url_for('list_bridges', tab='bridge'))

# --- PORT OPERATIONS (WITH TAB REDIRECT) ---
@app.route('/mikrotik/bridge/port/add', methods=['POST'])
def add_bridge_port():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        api.path('/interface/bridge/port').add(
            bridge=request.form.get('bridge'),
            interface=request.form.get('interface'),
            pvid=request.form.get('pvid', '1'),
            comment=request.form.get('comment')
        )
        flash("Port added successfully!", "success")
    except Exception as e:
        flash(f"Port Add Failed: {str(e)}", "danger")
    return redirect(url_for('list_bridges', tab='port'))

@app.route('/mikrotik/bridge/port/edit', methods=['POST'])
def edit_bridge_port():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        api.path('/interface/bridge/port').update(**{
            '.id': request.form.get('port_id'),
            'bridge': request.form.get('bridge'),
            'pvid': request.form.get('pvid'),
            'comment': request.form.get('comment')
        })
        flash("Port updated!", "success")
    except Exception as e:
        flash(f"Port Update Failed: {str(e)}", "danger")
    return redirect(url_for('list_bridges', tab='port'))

@app.route('/mikrotik/bridge/port/delete/<id>')
def delete_bridge_port(id):
    try:
        api = connect_to_mikrotik()
        api.path('/interface/bridge/port').remove(id)
        flash("Port removed!", "warning")
    except Exception as e:
        flash(f"Remove Error: {str(e)}", "danger")
    return redirect(url_for('list_bridges', tab='port'))

# --- VLAN OPERATIONS (WITH TAB REDIRECT) ---
@app.route('/mikrotik/bridge/vlan/add', methods=['POST'])
def add_bridge_vlan():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        tagged = request.form.getlist('tagged')
        untagged = request.form.getlist('untagged')
        
        data = {
            'bridge': request.form.get('bridge'),
            'vlan-ids': request.form.get('vlan_ids'),
            'comment': request.form.get('comment')
        }
        if tagged: data['tagged'] = ','.join(tagged)
        if untagged: data['untagged'] = ','.join(untagged)

        api.path('/interface/bridge/vlan').add(**data)
        flash("Bridge VLAN added!", "success")
    except Exception as e:
        flash(f"VLAN Add Failed: {str(e)}", "danger")
    return redirect(url_for('list_bridges', tab='vlan'))

@app.route('/mikrotik/bridge/vlan/edit', methods=['POST'])
def edit_bridge_vlan():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        tagged = request.form.getlist('tagged')
        untagged = request.form.getlist('untagged')
        
        api.path('/interface/bridge/vlan').update(**{
            '.id': request.form.get('vlan_internal_id'),
            'bridge': request.form.get('bridge'),
            'vlan-ids': request.form.get('vlan_ids'),
            'tagged': ','.join(tagged),
            'untagged': ','.join(untagged),
            'comment': request.form.get('comment')
        })
        flash("Bridge VLAN updated!", "success")
    except Exception as e:
        flash(f"VLAN Update Failed: {str(e)}", "danger")
    return redirect(url_for('list_bridges', tab='vlan'))

@app.route('/mikrotik/bridge/vlan/delete/<id>')
def delete_bridge_vlan(id):
    try:
        api = connect_to_mikrotik()
        api.path('/interface/bridge/vlan').remove(id)
        flash("VLAN entry deleted!", "warning")
    except Exception as e:
        flash(f"Delete Error: {str(e)}", "danger")
    return redirect(url_for('list_bridges', tab='vlan'))



####################### mikrotik VLAN ##########################################

@app.route('/mikrotik/networks/vlan')
def list_vlan():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        vlans = list(api.path('/interface/vlan').select())
        interfaces = list(api.path('/interface').select())
        return render_template('mikrotik_vlan.html', vlans=vlans, interfaces=interfaces)
    except Exception as e:
        return f"VLAN Load Error: {str(e)}"

###################### ADD VLAN###############################
@app.route('/mikrotik/networks/vlan/add', methods=['POST'])
def add_vlan():
    if 'target_ip' not in session: return redirect('/')
    
    try:
        v_name = request.form['name']
        v_id = request.form['vlan_id']
        v_interface = request.form['interface']
        api = connect_to_mikrotik()
        api.path('/interface/vlan').add(**{
            'name': v_name,
            'vlan-id': v_id,
            'interface': v_interface
        })
        
        return redirect(url_for('list_vlan'))
    except Exception as e:
        return f"VLAN Add Error: {str(e)} <br><a href='/mikrotik/networks/vlan'>Go Back</a>"

###################### DELETE VLAN #############################

@app.route('/mikrotik/networks/vlan/delete/<id>')
def delete_vlan(id):
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        api.path('/interface/vlan').remove(id)
        return redirect(url_for('list_vlan'))
    except Exception as e:
        return f"Delete Error: {str(e)}"

########################## EDIT VLAN ###########################

@app.route('/mikrotik/networks/vlan/edit', methods=['POST'])
def edit_vlan():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        vlan_internal_id = request.form['vlan_id_internal']
        api.path('/interface/vlan').update(**{
            '.id': vlan_internal_id,
            'name': request.form['name'],
            'vlan-id': request.form['vlan_id'],
            'interface': request.form['interface'],
            'mtu': request.form['mtu']
        })
        
        return redirect(url_for('list_vlan')) 
    except Exception as e:
        return f"VLAN Update Error: {str(e)}"

###################### DHCP SERVER & NETWORKS ###########################

@app.route('/mikrotik/networks/dhcp-server')
def list_dhcp_server():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        dhcp_servers = list(api.path('/ip/dhcp-server').select())
        networks = list(api.path('/ip/dhcp-server/network').select())
        pools = list(api.path('/ip/pool').select())
        interfaces = list(api.path('/interface').select())

        full_dhcp_data = []
        for srv in dhcp_servers:
            p_name = srv.get('address-pool')
            full_dhcp_data.append({
                '.id': srv.get('.id'),
                'name': srv.get('name'),
                'interface': srv.get('interface'),
                'pool_name': p_name,
                'disabled': srv.get('disabled')
            })

        return render_template('mikrotik_dhcp_server.html', 
                               servers=full_dhcp_data, networks=networks, 
                               interfaces=interfaces, pools=pools)
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
        return redirect(url_for('mikrotik_gui_main'))

# DHCP Server Ops
@app.route('/mikrotik/networks/dhcp-server/add', methods=['POST'])
def add_dhcp_server():
    try:
        api = connect_to_mikrotik()
        api.path('/ip/dhcp-server').add(name=request.form['name'], interface=request.form['interface'], **{'address-pool': request.form['pool']}, disabled='no')
        flash("Server added!", "success")
    except Exception as e: flash(f"Error: {e}", "danger")
    return redirect(url_for('list_dhcp_server', tab='servers'))

@app.route('/mikrotik/networks/dhcp-server/edit', methods=['POST'])
def edit_dhcp_server():
    try:
        api = connect_to_mikrotik()
        api.path('/ip/dhcp-server').update(**{'.id': request.form['server_id'], 'name': request.form['name'], 'interface': request.form['interface'], 'address-pool': request.form['pool']})
        flash("Server updated!", "success")
    except Exception as e: flash(f"Error: {e}", "danger")
    return redirect(url_for('list_dhcp_server', tab='servers'))

@app.route('/mikrotik/networks/dhcp-server/delete/<id>')
def delete_dhcp_server(id):
    try:
        api = connect_to_mikrotik()
        api.path('/ip/dhcp-server').remove(id)
        flash("Server deleted!", "warning")
    except Exception as e: flash(f"Error: {e}", "danger")
    return redirect(url_for('list_dhcp_server', tab='servers'))

# Network Ops (With Calculation)
@app.route('/mikrotik/networks/dhcp-network/add', methods=['POST'])
def add_dhcp_network():
    try:
        api = connect_to_mikrotik()
        try:
            net_obj = ipaddress.ip_network(f"{request.form['address']}/{request.form['netmask']}", strict=False)
            addr = str(net_obj)
        except: flash("Invalid IP/Mask", "danger"); return redirect(url_for('list_dhcp_server', tab='networks'))
        
        params = {'address': addr, 'gateway': request.form['gateway']}
        if request.form.get('dns'): params['dns-server'] = request.form['dns']
        if request.form.get('domain'): params['domain'] = request.form['domain']
        api.path('/ip/dhcp-server/network').add(**params)
        flash("Network added!", "success")
    except Exception as e: flash(f"Error: {e}", "danger")
    return redirect(url_for('list_dhcp_server', tab='networks'))

@app.route('/mikrotik/networks/dhcp-network/edit', methods=['POST'])
def edit_dhcp_network():
    try:
        api = connect_to_mikrotik()
        try:
            net_obj = ipaddress.ip_network(f"{request.form['address']}/{request.form['netmask']}", strict=False)
            addr = str(net_obj)
        except: flash("Invalid IP/Mask", "danger"); return redirect(url_for('list_dhcp_server', tab='networks'))
        
        params = {'.id': request.form['net_id'], 'address': addr, 'gateway': request.form['gateway'], 'dns-server': request.form['dns'], 'domain': request.form['domain']}
        api.path('/ip/dhcp-server/network').update(**params)
        flash("Network updated!", "success")
    except Exception as e: flash(f"Error: {e}", "danger")
    return redirect(url_for('list_dhcp_server', tab='networks'))

@app.route('/mikrotik/networks/dhcp-network/delete/<id>')
def delete_dhcp_network(id):
    try:
        api = connect_to_mikrotik()
        api.path('/ip/dhcp-server/network').remove(id)
        flash("Network deleted!", "warning")
    except Exception as e: flash(f"Error: {e}", "danger")
    return redirect(url_for('list_dhcp_server', tab='networks'))

# Pool Ops
@app.route('/mikrotik/networks/pool/add', methods=['POST'])
def add_pool():
    try:
        api = connect_to_mikrotik()
        api.path('/ip/pool').add(name=request.form['name'], ranges=request.form['ranges'])
        flash("Pool added!", "success")
    except Exception as e: flash(f"Error: {e}", "danger")
    return redirect(url_for('list_dhcp_server', tab='pools'))

@app.route('/mikrotik/networks/pool/edit', methods=['POST'])
def edit_pool():
    try:
        api = connect_to_mikrotik()
        api.path('/ip/pool').update(**{'.id': request.form['pool_id'], 'name': request.form['name'], 'ranges': request.form['ranges']})
        flash("Pool updated!", "success")
    except Exception as e: flash(f"Error: {e}", "danger")
    return redirect(url_for('list_dhcp_server', tab='pools'))

@app.route('/mikrotik/networks/pool/delete/<id>')
def delete_pool(id):
    try:
        api = connect_to_mikrotik()
        api.path('/ip/pool').remove(id)
        flash("Pool deleted!", "warning")
    except Exception as e: flash(f"Error: {e}", "danger")
    return redirect(url_for('list_dhcp_server', tab='pools'))

# Wizard
@app.route('/mikrotik/networks/dhcp-server/setup', methods=['POST'])
def dhcp_setup_mikrotik():
    try:
        api = connect_to_mikrotik()
        
        # Get Inputs
        iface = request.form['interface']
        gw = request.form['gateway']
        mask = request.form['netmask']
        rng = request.form['ip_range']
        dns = request.form['dns']
        
        # New Input: Lease Time
        lease = request.form.get('lease_time', '1h') # Default 1h if missing

        # Validate Network
        try:
            net_obj = ipaddress.ip_network(f"{gw}/{mask}", strict=False)
            net_addr = str(net_obj)
        except: 
            flash("Invalid Config", "danger")
            return redirect(url_for('list_dhcp_server'))

        # 1. Pool
        pool_name = f"pool_{iface}"
        try: 
            p = next((p for p in list(api.path('/ip/pool').select()) if p['name'] == pool_name), None)
            if p: api.path('/ip/pool').update(**{'.id': p['.id'], 'ranges': rng})
            else: api.path('/ip/pool').add(name=pool_name, ranges=rng)
        except: pass

        # 2. Network
        try:
            n = next((n for n in list(api.path('/ip/dhcp-server/network').select()) if n.get('address') == net_addr), None)
            np = {'address': net_addr, 'gateway': gw, 'dns-server': dns}
            if n: 
                np['.id'] = n['.id']
                api.path('/ip/dhcp-server/network').update(**np)
            else: 
                api.path('/ip/dhcp-server/network').add(**np)
        except: pass

        # 3. Server (With Lease Time)
        try:
            api.path('/ip/dhcp-server').add(
                name=f"dhcp_{iface}", 
                interface=iface, 
                **{'address-pool': pool_name, 'lease-time': lease}, # Updated Here
                disabled='no'
            )
            flash("Wizard Completed!", "success")
        except: flash("Server Exists/Error", "warning")

    except Exception as e: flash(f"Wizard Error: {e}", "danger")
    return redirect(url_for('list_dhcp_server', tab='servers'))

###########################DHCP LEASES############################
@app.route('/mikrotik/networks/dhcp-leases')
def list_dhcp_leases():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        leases = list(api.path('/ip/dhcp-server/lease').select())
        return render_template('mikrotik_dhcp_lease.html', leases=leases)
    except Exception as e:
        return f"Lease Load Error: {str(e)}"

########################### Lease Create #####################
@app.route('/mikrotik/networks/dhcp-leases/make-static', methods=['POST'])
def make_lease_static():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        api.path('/ip/dhcp-server/lease').add(**{
            'address': request.form['address'],
            'mac-address': request.form['mac'],
            'server': request.form['server'],
            'comment': 'Static via Web Panel'
        })
        return redirect(url_for('list_dhcp_leases'))
    except Exception as e:
        return f"Static Lease Error: {str(e)}"

########################### Lease DELETE #####################

@app.route('/mikrotik/networks/dhcp-leases/delete/<id>')
def delete_lease(id):
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        api.path('/ip/dhcp-server/lease').remove(id)
        return redirect(url_for('list_dhcp_leases'))
    except Exception as e:
        return f"Delete Error: {str(e)}"

############################ LEASE EDIT #########################

@app.route('/mikrotik/networks/dhcp-leases/edit', methods=['POST'])
def edit_lease():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik()
        lease_id = request.form['lease_id']
        try:
            api.path('/ip/dhcp-server/lease').call('make-static', {'.id': lease_id})
        except:
            pass

        api.path('/ip/dhcp-server/lease').update(**{
            '.id': lease_id,
            'address': request.form['address'],
            'mac-address': request.form['mac'],
            'server': request.form['server'],
            'comment': request.form['comment']
        })
        
        return redirect(url_for('list_dhcp_leases'))
    except Exception as e:
        return f"Lease Update Error: {str(e)}"

###################FIREWALL###############

# ----------------- ADD IP -----------------
@app.route('/mikrotik/firewall')
def firewall_page():
    if 'target_ip' not in session: return redirect('/')
    
    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))   
        addresses = list(api.path('/ip/firewall/address-list').select())
        nat_rules = list(api.path('/ip/firewall/nat').select())
        return render_template('mikrotik_firewall.html', addresses=addresses, nat_rules=nat_rules)
    except Exception as e:
        flash(f"Connection Error: {str(e)}", "danger")
        return redirect('/dashboard')

#########################IP Add ################################
@app.route('/mikrotik/firewall/add', methods=['POST'])
def add_firewall_ip():
    if 'target_ip' not in session: return redirect('/')
    ip = request.form.get('ip')
    list_name = request.form.get('list_name')
    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))   
        api.path('/ip/firewall/address-list').add(address=ip, list=list_name)
        flash(f"IP {ip} added to {list_name}", "success")
    except Exception as e:
        flash(f"Add Failed: {str(e)}", "danger")
    return redirect(url_for('firewall_page'))

#########################IP Update ###################
@app.route('/mikrotik/firewall/address/update', methods=['POST'])
def update_firewall_ip():
    if 'target_ip' not in session: return redirect('/')
    addr_id = request.form.get('id')
    new_ip = request.form.get('address')
    new_list = request.form.get('list')
    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))   
        api.path('/ip/firewall/address-list').update(**{
            '.id': addr_id,
            'address': new_ip,
            'list': new_list
        })
        flash("Address Updated Successfully!", "success")
    except Exception as e:
        flash(f"Update Failed: {str(e)}", "danger")
    return redirect(url_for('firewall_page'))

# IP Remove
@app.route('/mikrotik/firewall/remove', methods=['POST'])
def remove_firewall_ip():
    if 'target_ip' not in session: return redirect('/')
    addr_id = request.form.get('id')
    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))   
        api.path('/ip/firewall/address-list').remove(addr_id)
        flash("Removed successfully", "success")
    except Exception as e:
        flash(f"Remove Failed: {str(e)}", "danger")
    return redirect(url_for('firewall_page'))

############################### NAT ###############################
@app.route('/mikrotik/firewall/nat')
def nat_page():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))   
        nat_rules = list(api.path('/ip/firewall/nat').select())
        return render_template('mikrotik_nat.html', nat_rules=nat_rules)
    except Exception as e:
        print(f"NAT Fetch Error: {e}")
        return f"Error loading NAT: {e}"

# ################ NAT IP ADD ###########################
@app.route('/mikrotik/firewall/nat/add', methods=['POST'])
def add_nat():
    chain = request.form.get('chain')
    out_iface = request.form.get('out_interface')
    action = request.form.get('action')
    api = connect_to_mikrotik() 
    api.path('/ip/firewall/nat').add(chain=chain, **{"out-interface": out_iface}, action=action)
    
    return redirect(url_for('firewall_page'))

# ################ mikrotik firewall nat remove ###########################
@app.route('/mikrotik/firewall/nat/remove', methods=['POST'])
def remove_nat():
    rule_id = request.form.get('id')
    api = connect_to_mikrotik() 
    api.path('/ip/firewall/nat').remove(rule_id)
    return redirect(url_for('nat_page'))

#################### mikrotik ISP #####################################
@app.route('/mikrotik/isp-setup', methods=['GET', 'POST'])
def isp_setup():
    if 'target_ip' not in session: return redirect('/')
    
    try:
        api = connect_to_mikrotik()
    except:
        return redirect(url_for('logout'))
    if request.method == 'POST':
        try:
            c_type = request.form['conn_type']
            interface = request.form['interface']
            try:
                api.path('/ip/firewall/nat').add(chain='srcnat', **{'out-interface': interface}, action='masquerade', comment="ISP-WAN")
            except: pass

            if c_type == 'static':
                api.path('/ip/address').add(address=request.form['static_ip'], interface=interface)
                api.path('/ip/route').add(gateway=request.form['static_gw'], **{'dst-address': '0.0.0.0/0'})
                try: api.path('/ip/dns').set(servers=request.form['static_dns'])
                except: pass
            
            elif c_type == 'dhcp':
                api.path('/ip/dhcp-client').add(interface=interface, **{'add-default-route': 'yes', 'disabled': 'no'})

            elif c_type == 'pppoe':
                api.path('/interface/pppoe-client').add(
                    name="pppoe-out1", interface=interface, 
                    user=request.form['pppoe_user'], password=request.form['pppoe_pass'], 
                    **{'add-default-route': 'yes', 'disabled': 'no'}
                )
            
            flash("Configuration Applied!", "success")
            return redirect(url_for('isp_setup')) 
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
            return redirect(url_for('isp_setup'))
    interfaces = list(api.path('/interface').select())
    
    wan_info = {
        'ip': 'Searching...',
        'gateway': 'Checking...',
        'dns': 'Checking...',
        'status': 'Checking...'
    }

    try:
        all_ips = list(api.path('/ip/address').select())
        routes = list(api.path('/ip/route').select())
        active_route = next((r for r in routes if r.get('dst-address') == '0.0.0.0/0' and str(r.get('active')) == 'true'), None)
        
        wan_iface_name = None

        if active_route:
            wan_info['status'] = 'Connected'
            wan_info['gateway'] = active_route.get('gateway', 'Unknown')
            gw_status = active_route.get('gateway-status', '')
            for iface in interfaces:
                if iface['name'] in gw_status:
                    wan_iface_name = iface['name']
                    break
        else:
            wan_info['status'] = 'Disconnected'
        if wan_iface_name:
            target_ip = next((i for i in all_ips if i.get('interface') == wan_iface_name), None)
            if target_ip:
                wan_info['ip'] = target_ip.get('address')
        else:
            ether1_ip = next((i for i in all_ips if i.get('interface') == 'ether1'), None)
            if ether1_ip:
                wan_info['ip'] = ether1_ip.get('address')
                if wan_info['status'] == 'Checking...': wan_info['status'] = 'Connected (Assumed)'
        dns = list(api.path('/ip/dns').select())
        if dns:
            wan_info['dns'] = dns[0].get('dynamic-servers') or dns[0].get('servers')

    except Exception as e:
        print(f"Debug Error: {e}")
        wan_info['ip'] = "Error"

    return render_template('mikrotik_isp.html', interfaces=interfaces, wan_info=wan_info)


########################## Mikrotik Identity & Location #####################
@app.route('/mikrotik/system/identity', methods=['GET', 'POST'])
def system_identity():
    if 'target_ip' not in session: return redirect('/')
    api = connect_to_mikrotik()

    # Paths
    identity_path = api.path('/system/identity')
    note_path = api.path('/system/note')
    
    if request.method == 'POST':
        try:
            identity_path.update(name=request.form['identity'])
            contact_data = {
                'name': request.form['admin_name'],
                'email': request.form['email'],
                'addr1': request.form['addr1'],
                'addr2': request.form['addr2'],
                'city': request.form['city'],
                'zip': request.form['zip'],
                'country': request.form['country']
            }
            
            note_path.update(note=json.dumps(contact_data))
            
            return redirect(url_for('system_identity'))
        except Exception as e:
            return f"Error: {str(e)}"

    identity = list(identity_path.select())[0]
    note_record = list(note_path.select())
    
    contact_info = {'name':'', 'email':'', 'addr1':'', 'addr2':'', 'city':'', 'zip':'', 'country':''}
    if note_record and note_record[0].get('note'):
        try:
            contact_info = json.loads(note_record[0]['note'])
        except:
            pass 

    return render_template('mikrotik_identity.html', identity=identity, contact_info=contact_info)

######################### Mikrotik Clock #######################################

@app.route('/mikrotik/system/clock', methods=['GET', 'POST'])
def system_clock():
    if 'target_ip' not in session: return redirect('/')
    api = connect_to_mikrotik()
    
    path_clock = api.path('/system/clock')
    path_ntp = api.path('/system/ntp/client')
    
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'update_clock':
                path_clock.update(**{
                    'time-zone-name': request.form['timezone'],
                    'time-zone-autodetect': 'yes' if request.form.get('autodetect') else 'no'
                })
                if request.form.get('manual_time'):
                    path_clock.update(time=request.form['manual_time'])

            elif action == 'update_ntp':
                path_ntp.update(**{
                    'enabled': 'yes' if request.form.get('ntp_enabled') else 'no',
                    'primary-ntp': request.form['primary_ntp'],
                    'secondary-ntp': request.form['secondary_ntp']
                })
            
            return redirect(url_for('system_clock'))
        except Exception as e:
            return f"Error: {str(e)}"

    clock_data = list(path_clock.select())[0]
    ntp_data = list(path_ntp.select())[0]
    timezones = ["Asia/Dhaka", "Asia/Dubai", "Asia/Singapore", "UTC", "America/New_York", "Europe/London"]
    
    return render_template('mikrotik_clock.html', clock=clock_data, ntp=ntp_data, timezones=timezones)

############################### Mikrotik user #################################

@app.route('/mikrotik/system/users')
def system_users():
    if 'target_ip' not in session: return redirect('/')
    api = connect_to_mikrotik()
    
    try:
        users = list(api.path('user').select()) 
        groups = list(api.path('user', 'group').select())
        return render_template('mikrotik_users.html', users=users, groups=groups)
        
    except Exception:
        try:
            users = list(api.path('system').path('user').select())
            groups = list(api.path('system').path('user').path('group').select())
            return render_template('mikrotik_users.html', users=users, groups=groups)
        except Exception as e:
            print(f"Final Debug Error: {e}")
            return f"Error: Router can't recognise '/system/user'।"

#################################### user add ##############################

@app.route('/mikrotik/system/users/add', methods=['POST'])
def add_router_user():
    if 'target_ip' not in session: return redirect('/')
    api = connect_to_mikrotik()
    
    try:
        username = request.form.get('username')
        password = request.form.get('password')
        group = request.form.get('group')
        comment = request.form.get('comment', 'Added via Web Panel')
        try:
            api.path('system', 'user').add(
                name=username,
                password=password,
                group=group,
                comment=comment
            )
        except:
            api.path('user').add(
                name=username,
                password=password,
                group=group,
                comment=comment
            )
            
        return redirect(url_for('system_users'))
        
    except Exception as e:
        return f"Error adding user: {str(e)}"

##################################user edit #############################

@app.route('/mikrotik/system/users/edit', methods=['POST'])
def edit_router_user():
    if 'target_ip' not in session: return redirect('/')
    api = connect_to_mikrotik()
    
    try:
        user_id = request.form.get('user_id')
        new_group = request.form.get('group')
        new_password = request.form.get('password')
        comment = request.form.get('comment')
        params = {
            '.id': user_id, 
            'group': new_group, 
            'comment': comment
        }

        if new_password and new_password.strip():
            params['password'] = new_password
        try:
            api.path('system', 'user').update(**params)
        except:
            api.path('user').update(**params)
        
        return redirect(url_for('system_users'))
        
    except Exception as e:
        return f"Update Error: {str(e)}"


# --- User Enable/Disable (Toggle) ---
@app.route('/mikrotik/system/users/set_status/<user_id>/<action>')
def set_router_user_status(user_id, action):
    if 'target_ip' not in session: return redirect('/')
    api = connect_to_mikrotik()
    
    status_value = 'no' if action == 'enable' else 'yes'
    
    try:
        try:
            api.path('system', 'user').update(**{'.id': user_id, 'disabled': status_value})
        except:
            api.path('user').update(**{'.id': user_id, 'disabled': status_value})
            
        return redirect(url_for('system_users'))
    except Exception as e:
        print(f"Status Update Error: {e}")
        return f"Error: {str(e)}"




# --- Delete User  ---
@app.route('/mikrotik/system/users/delete')
def delete_router_user():
    if 'target_ip' not in session: return redirect('/')
    api = connect_to_mikrotik()
    
    user_id = request.args.get('id')
    user_name = request.args.get('name')

    if user_name == 'admin':
        return "Error: Cannot delete default admin user."

    try:
        try:
            api.path('system', 'user').remove(user_id)
        except:
            api.path('user').remove(user_id)
        return redirect(url_for('system_users'))
    except Exception as e:
        return f"Delete Error: {str(e)}"


        
#######################BACKUP/RESTORE######################

def run_ssh_command(command):
    host = session.get('target_ip')
    user = session.get('target_user')
    password = session.get('target_pass')
    port = 22 
    
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=port, username=user, password=password, timeout=10)
        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()
        
        client.close()
        
        if error:
            print(f"SSH Error: {error}")
            return False, error
        return True, output
    except Exception as e:
        print(f"SSH Connection Failed: {e}")
        return False, str(e)

@app.route('/mikrotik/system/backup')
def backup_page():
    if 'target_ip' not in session: return redirect('/')
    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))   
        files = api.path('file')
        all_files = list(files.select())
        
        backups = []
        for f in all_files:
            if f.get('name', '').endswith('.backup'):
                size = int(f.get('size', 0))
                h_size = f"{round(size/1024, 2)} KB" if size < 1048576 else f"{round(size/1048576, 2)} MB"
                
                backups.append({
                    'name': f.get('name'),
                    'size': h_size,
                    'time': f.get('creation-time', 'N/A')
                })
        backups.sort(key=lambda x: x['time'], reverse=True)
        return render_template('mikrotik_backup.html', backups=backups)
    except:
        return redirect(url_for('mikrotik_gui_main'))

@app.route('/mikrotik/system/backup/create', methods=['POST'])
def create_backup():
    if 'target_ip' not in session: return redirect('/')
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    name = request.form.get('filename', 'backup').strip().replace(" ", "_")
    if name.endswith('.backup'): name = name[:-7]
    final_name = f"{name}-{timestamp}.backup"

    cmd = f'/system backup save name="{final_name}" dont-encrypt=yes'
    
    success, msg = run_ssh_command(cmd)

    if success:
        time.sleep(2)
        flash(f"Backup '{final_name}' created successfully!", "success")
    else:
        flash(f"Failed: {msg}", "danger")
        
    return redirect(url_for('backup_page'))

@app.route('/mikrotik/system/backup/delete')
def delete_backup():
    if 'target_ip' not in session: return redirect('/')
    filename = request.args.get('name')
    cmd = f'/file remove [find name="{filename}"]'
    
    success, msg = run_ssh_command(cmd)
    
    if success:
        time.sleep(1)
        flash(f"Deleted {filename}", "warning")
    else:
        flash(f"Delete Failed: {msg}", "danger")
        
    return redirect(url_for('backup_page'))

@app.route('/mikrotik/system/backup/restore/<name>')
def restore_backup(name):
    if 'target_ip' not in session: return redirect('/')
    
    host = session.get('target_ip')
    user = session.get('target_user')
    password = session.get('target_pass')
    
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=user, password=password, timeout=5)
        cmd = f'/system backup load name="{name}" dont-ask=yes'
        client.exec_command(cmd)
        time.sleep(1)        
        client.close()
        flash(f"Restore initiated for '{name}'. Router is rebooting now...", "success")
        
    except Exception as e:
        print(f"Restore Log (Connection dropped expected): {e}")
        flash(f"Restore command sent! Router is rebooting. Please wait 1-2 minutes.", "warning")

    return redirect(url_for('mikrotik_gui_main')) 
############################### Mikrotik REBOOT#######################



@app.route('/mikrotik/system/reboot', methods=['GET', 'POST'])
def reboot_router():
    if 'target_ip' not in session: return redirect('/')
    
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(session['target_ip'], username=session['target_user'], password=session['target_pass'], timeout=10)
            
            cmd = "/system reboot\ny" if action == 'reboot' else "/system shutdown\ny"
            ssh.exec_command(cmd)
            ssh.close()
            session.clear()
            return redirect(url_for('home'))
        except Exception as e:
            flash(f"Connection Error: {str(e)}", "danger")
            return redirect(url_for('reboot_router'))

    schedules = []
    try:
        api = connect_to_mikrotik()
        all_sched = api.path('/system/scheduler').select('.id', 'name', 'start-time', 'interval', 'next-run')
        schedules = [s for s in all_sched if s.get('name', '').startswith('maint_')]
    except Exception as e:
        print(f"Error fetching schedules: {e}")

    return render_template('mikrotik_reboot.html', schedules=schedules)


@app.route('/mikrotik/system/maintenance/schedule', methods=['POST'])
def save_maintenance_schedule():
    if 'target_ip' not in session: return redirect('/')
    
    sched_id = request.form.get('sched_id')
    raw_datetime = request.form.get('full_datetime') 
    interval = request.form.get('interval_select')
    
    try:
        dt_obj = datetime.strptime(raw_datetime, "%Y-%m-%d %H:%M")
        mt_date = dt_obj.strftime("%b/%d/%Y") 
        mt_time = dt_obj.strftime("%H:%M:%S")
        sched_name = f"maint_{dt_obj.strftime('%Y%m%d_%H%M')}"
        
        api = connect_to_mikrotik()
        path_sched = api.path('/system/scheduler')
        
        params = {
            'name': sched_name,
            'start-date': mt_date,
            'start-time': mt_time,
            'interval': interval,
            'on-event': '/system reboot' 
        }
        
        if sched_id: 
            params['.id'] = sched_id
            path_sched.update(**params)
            flash(f"Schedule updated: {mt_date} at {mt_time}", "success")
        else: 
            path_sched.add(**params)
            flash(f"New maintenance scheduled for {mt_date}!", "success")
            
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
        print(e)
        
    return redirect(url_for('reboot_router'))
@app.route('/mikrotik/system/maintenance/delete/<id>', methods=['POST'])
def delete_maintenance(id):
    try:
        api = connect_to_mikrotik()
        api.path('/system/scheduler').remove(id)
        flash("Schedule deleted successfully!", "warning")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    
    return redirect(url_for('reboot_router'))

    
# ############################# MIKROTIK RADIUS MANAGER ################# #



def format_bytes(size):
    if not size or size == '0': return "0 B"
    try:
        size = int(size)
        for unit in ['', 'K', 'M', 'G', 'T']:
            if abs(size) < 1024.0:
                return f"{size:.2f} {unit}B"
            size /= 1024.0
        return f"{size:.2f} PB"
    except:
        return "0 B"

@app.route('/mikrotik/radius/users', methods=['GET', 'POST'])
def hotspot_users():
    if 'target_ip' not in session: return redirect('/') 

    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))

        user_api = api.path('ip', 'hotspot', 'user')
        profile_api = api.path('ip', 'hotspot', 'user', 'profile')
        server_api = api.path('ip', 'hotspot') 
    except Exception as e:
        flash(f"Connection Failed: {e}", "danger")
        return redirect(url_for('mikrotik_gui_main'))

    # --- ADD & EDIT REQUEST ---
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')
            profile = request.form.get('profile') 
            server = request.form.get('server')  
            full_name = f"{request.form.get('fname', '')} {request.form.get('lname', '')}".strip()

            if request.form.get('add_user') == '1':
                user_api.add(
                    name=username,
                    password=password,
                    profile=profile,
                    server=server,
                    comment=full_name
                )
                flash(f"User '{username}' created successfully!", "success")

            elif request.form.get('edit_user') == '1':
                uid = request.form.get('user_id')
                update_data = {
                    '.id': uid,
                    'name': username,
                    'profile': profile,
                    'server': server,
                    'comment': full_name
                }
                if password: 
                    update_data['password'] = password
                
                user_api.update(**update_data)
                flash("User details updated successfully!", "success")
                
        except Exception as e:
            flash(f"Operation Error: {e}", "danger")
        
        return redirect(url_for('hotspot_users'))

    # --- DELETE REQUEST (FIXED) ---
    if request.args.get('action') == 'delete':
        try:
            uid = request.args.get('id')
            if uid:
                user_api.remove(uid) 
                flash(f"User deleted successfully!", "warning")
            else:
                flash("User ID not found!", "danger")
        except Exception as e:
            flash(f"Delete Error: {str(e)}", "danger")
        
        return redirect(url_for('hotspot_users'))
    user_list = []
    profiles = []
    servers = []

    try:
        users_raw = list(user_api.select())
        profiles_raw = list(profile_api.select())
        servers_raw = list(server_api.select()) 
        
        for u in users_raw:
            parts = u.get('comment', '').split(' ')
            fname = parts[0] if len(parts) > 0 else ''
            lname = parts[1] if len(parts) > 1 else ''

            user_list.append({
                'id': u.get('.id'),
                'username': u.get('name'),
                'password': u.get('password', '****'),
                'profile': u.get('profile', 'default'),
                'server': u.get('server', 'all'),
                'fname': fname,
                'lname': lname,
                'uptime': u.get('uptime', '0s'),
                'dl': format_bytes(u.get('bytes-out', '0')),
                'ul': format_bytes(u.get('bytes-in', '0'))
            })
            
        profiles = [p.get('name') for p in profiles_raw]
        servers = [s.get('name') for s in servers_raw]
        if 'all' not in servers: servers.insert(0, 'all')

    except Exception as e:
        flash(f"Data Loading Error: {e}", "danger")

    return render_template('mikrotik_radius_user.html', users=user_list, profiles=profiles, servers=servers)



# ############################# RADIUS / HOTSPOT PROFILE MANAGER ################# #

# 1. Rate Limit Parser
def parse_rate_limit_advanced(rate_str):
    data = {
        'max_up': '', 'max_down': '',
        'burst_up': '', 'burst_down': '',
        'thresh_up': '', 'thresh_down': '',
        'time_up': '', 'time_down': '',
        'prio': '',
        'min_up': '', 'min_down': ''
    }
    if not rate_str: return data
    parts = rate_str.split(' ')
    if len(parts) > 0 and '/' in parts[0]: data['max_up'], data['max_down'] = parts[0].split('/')
    if len(parts) > 1 and '/' in parts[1]: data['burst_up'], data['burst_down'] = parts[1].split('/')
    if len(parts) > 2 and '/' in parts[2]: data['thresh_up'], data['thresh_down'] = parts[2].split('/')
    if len(parts) > 3 and '/' in parts[3]: data['time_up'], data['time_down'] = parts[3].split('/')
    if len(parts) > 4: data['prio'] = parts[4]
    if len(parts) > 5 and '/' in parts[5]: data['min_up'], data['min_down'] = parts[5].split('/')
    return data

def parse_time_struct(time_str):
    res = {'d': 0, 'h': 0, 'm': 0}
    if not time_str: return res
    
    try:
        time_part = time_str
        if 'd' in time_str:
            parts = time_str.split('d')
            res['d'] = int(parts[0])
            time_part = parts[1].strip()

        if ':' in time_part:
            t_parts = time_part.split(':')
            if len(t_parts) >= 2:
                res['h'] = int(t_parts[0])
                res['m'] = int(t_parts[1])
    except:
        pass 
    return res
def build_time_str(d, h, m):
    try:
        d, h, m = int(d), int(h), int(m)
        if d == 0 and h == 0 and m == 0: return None
        
        time_part = f"{h:02}:{m:02}:00"
        if d > 0:
            return f"{d}d {time_part}"
        else:
            return time_part
    except:
        return None

# 4. Main Route Function
@app.route('/mikrotik/radius/profiles', methods=['GET', 'POST'])
def radius_profiles():
    if 'target_ip' not in session: return redirect('/') 

    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))

    except Exception as e:
        flash(f"Connection Failed: {e}", "danger")
        return redirect(url_for('mikrotik_gui_main'))

    profile_api = api.path('ip', 'hotspot', 'user', 'profile')
    pool_api = api.path('ip', 'pool')

    # --- POST REQUEST (Add / Edit) ---
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            price = request.form.get('price', '0')
            addr_pool = request.form.get('pool')
            shared_users = request.form.get('shared_users')
            
            session_str = build_time_str(request.form.get('session_d', 0), request.form.get('session_h', 0), request.form.get('session_m', 0))
            idle_str = build_time_str(request.form.get('idle_d', 0), request.form.get('idle_h', 0), request.form.get('idle_m', 0))
            keep_str = build_time_str(request.form.get('keep_d', 0), request.form.get('keep_h', 0), request.form.get('keep_m', 0))
            max_up = request.form.get('limit_up', '')
            max_down = request.form.get('limit_down', '')
            rate_string = ""
            if max_up and max_down:
                rate_string = f"{max_up}/{max_down}"
                burst_up = request.form.get('burst_up', '')
                burst_down = request.form.get('burst_down', '')
                thresh_up = request.form.get('thresh_up', '')
                thresh_down = request.form.get('thresh_down', '')
                time_up = request.form.get('time_up', '')
                time_down = request.form.get('time_down', '')
                prio = request.form.get('priority', '')
                min_up = request.form.get('min_up', '')
                min_down = request.form.get('min_down', '')

                if burst_up and burst_down:
                    rate_string += f" {burst_up}/{burst_down}"
                    if thresh_up and thresh_down:
                        rate_string += f" {thresh_up}/{thresh_down}"
                        if time_up and time_down:
                            rate_string += f" {time_up}/{time_down}"
                            if prio:
                                rate_string += f" {prio}"
                                if min_up and min_down:
                                    rate_string += f" {min_up}/{min_down}"

            price_script = f"#PRICE:{price}"
            profile_data = {
                'name': name,
                'on-login': price_script,
                'address-pool': addr_pool if addr_pool != 'none' else None,
                'shared-users': shared_users,
                'rate-limit': rate_string if rate_string else None,
                'session-timeout': session_str,
                'idle-timeout': idle_str,
                'keepalive-timeout': keep_str
            }
            
            cleaned_data = {k: v for k, v in profile_data.items() if v is not None and v != ""}

            if 'add_profile' in request.form:
                profile_api.add(**cleaned_data)
                flash(f"Package '{name}' created successfully!", "success")

            elif 'edit_profile' in request.form:
                pid = request.form.get('profile_id')
                cleaned_data['.id'] = pid
                if name == 'default':
                    if 'name' in cleaned_data: del cleaned_data['name']
                profile_api.update(**cleaned_data)
                flash(f"Package updated successfully!", "success")

        except Exception as e:
            flash(f"Operation Error: {e}", "danger")
        
        return redirect(url_for('radius_profiles'))

    # --- DELETE REQUEST ---
    if request.args.get('action') == 'delete':
        try:
            pid = request.args.get('id')
            name = request.args.get('name')
            if name == 'default':
                flash("Cannot delete default profile!", "danger")
            elif pid:
                profile_api.remove(pid)
                flash("Profile deleted!", "warning")
        except Exception as e:
            flash(f"Delete Error: {e}", "danger")
        return redirect(url_for('radius_profiles'))

    # --- GET REQUEST ---
    profiles = []
    pools = []
    try:
        profiles_raw = list(profile_api.select())
        pools_raw = list(pool_api.select())
        
        for p in pools_raw: pools.append(p.get('name'))

        for p in profiles_raw:
            rate_raw = p.get('rate-limit', '')
            bw_data = parse_rate_limit_advanced(rate_raw)
            
            # Price Extraction
            script_content = p.get('on-login', '')
            display_price = '0'
            if script_content and '#PRICE:' in script_content:
                try: display_price = script_content.split('#PRICE:')[1].strip()
                except: pass

            # Time Parsing for Dropdowns
            sess_time = parse_time_struct(p.get('session-timeout', ''))
            idle_time = parse_time_struct(p.get('idle-timeout', ''))
            keep_time = parse_time_struct(p.get('keepalive-timeout', ''))

            profiles.append({
                'id': p.get('.id'),
                'name': p.get('name'),
                'price': display_price,
                'pool': p.get('address-pool', 'none'),
                'shared_users': p.get('shared-users', '1'),
                'rate_limit': rate_raw,
                'session_str': p.get('session-timeout', '-'),
                't_sess': sess_time,
                't_idle': idle_time, 
                't_keep': keep_time,
                
                'bw': bw_data
            })
    except Exception as e:
        flash(f"Data Loading Error: {e}", "danger")

    return render_template('mikrotik_radius_profile.html', profiles=profiles, pools=pools)



# ############################# HOTSPOT ACTIVE HOSTS / USERS MANAGER ################# #

@app.route('/mikrotik/hotspot/active', methods=['GET', 'POST'])
def hotspot_active():
    if 'target_ip' not in session: return redirect('/') 

    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))

    except Exception as e:
        flash(f"Connection Failed: {e}", "danger")
        return redirect(url_for('mikrotik_gui_main'))

    host_api = api.path('ip', 'hotspot', 'host')
    active_api = api.path('ip', 'hotspot', 'active')
    binding_api = api.path('ip', 'hotspot', 'ip-binding')

    # --- ACTIONS (Bypass, Block, Remove) ---
    if request.args.get('action') and request.args.get('mac'):
        mac = request.args.get('mac')
        action = request.args.get('action')
        
        try:
            if action == 'bypass':
                binding_api.add(mac_address=mac, type='bypassed', comment='Bypassed via Web')
                flash(f"Device {mac} Bypassed Successfully!", "success")
                
            elif action == 'block':
                binding_api.add(mac_address=mac, type='blocked', comment='Blocked via Web')
                flash(f"Device {mac} Blocked Successfully!", "danger")
                
            elif action == 'remove':
                host_id = request.args.get('id')
                host_api.remove(host_id)
                flash(f"Host {mac} removed/kicked!", "warning")
                
            try:
                hst = host_api.select(where={'mac-address': mac})
                for h in hst: host_api.remove(h['.id'])
            except: pass

        except Exception as e:
            flash(f"Action Failed: {e}", "danger")
            
        return redirect(url_for('hotspot_active'))
    hosts_list = []
    try:
        hosts_raw = list(host_api.select())
    
        active_users = {u.get('mac-address'): u.get('user') for u in list(active_api.select())}
        
        bindings = {b.get('mac-address'): b.get('type') for b in list(binding_api.select()) if b.get('mac-address')}

        for h in hosts_raw:
            mac = h.get('mac-address')
            ip = h.get('address')
            status = "Unauthenticated"
            username = "-"
            row_class = ""
            
            if mac in active_users:
                status = "Authenticated"
                username = active_users[mac]
                row_class = "table-success" 
            elif mac in bindings:
                b_type = bindings[mac]
                if b_type == 'bypassed':
                    status = "Bypassed"
                    username = "(Device)"
                    row_class = "table-primary" 
                elif b_type == 'blocked':
                    status = "Blocked"
                    row_class = "table-danger" 

            hosts_list.append({
                'id': h.get('.id'),
                'mac': mac,
                'ip': ip,
                'server': h.get('server', '-'),
                'username': username,
                'hostname': h.get('host-name', '-'), # ডিভাইস নাম (e.g. Galaxy-A50)
                'uptime': h.get('uptime', '0s'),
                'idle': h.get('idle-timeout', '0s'), # Idle time
                'bytes_in': format_bytes(h.get('bytes-in', 0)),
                'bytes_out': format_bytes(h.get('bytes-out', 0)),
                'status': status,
                'row_class': row_class,
                'comment': h.get('comment', '')
            })

    except Exception as e:
        flash(f"Data Error: {e}", "danger")

    return render_template('mikrotik_active_hosts.html', hosts=hosts_list)



###############################POPRT FORWARDING######################


@app.route('/mikrotik/firewall/port-forwarding', methods=['GET', 'POST'])
def port_forwarding():
    if 'target_ip' not in session: return redirect('/') 

    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))

    except Exception as e:
        flash(f"Connection Failed: {e}", "danger")
        return redirect(url_for('mikrotik_gui_main'))
    nat_api = api.path('ip', 'firewall', 'nat')
    if request.method == 'POST':
        try:
            ext_port = request.form.get('ext_port')
            protocol = request.form.get('protocol')
            int_address = request.form.get('int_address')
            int_port = request.form.get('int_port')
            comment = request.form.get('comment', '')
            nat_data = {
                'chain': 'dstnat',
                'protocol': protocol,
                'dst-port': ext_port,
                'action': 'dst-nat',
                'to-addresses': int_address,
                'to-ports': int_port,
                'comment': comment
            }

            if 'add_rule' in request.form:
                nat_api.add(**nat_data)
                flash("New DST-NAT rule added successfully!", "success")
            elif 'edit_rule' in request.form:
                rule_id = request.form.get('rule_id')
                nat_data['.id'] = rule_id
                nat_api.update(**nat_data)
                flash("DST-NAT rule updated successfully!", "success")

        except Exception as e:
            flash(f"Operation Error: {e}", "danger")
        
        return redirect(url_for('port_forwarding'))
    if request.args.get('action') == 'delete':
        try:
            rule_id = request.args.get('id')
            if rule_id:
                nat_api.remove(rule_id)
                flash("Rule deleted successfully!", "warning")
        except Exception as e:
            flash(f"Delete Error: {e}", "danger")
        return redirect(url_for('port_forwarding'))
    rules_list = []
    try:
        all_nat = list(nat_api.select())
        for r in all_nat:
            if r.get('chain') == 'dstnat' and r.get('action') == 'dst-nat':
                rules_list.append({
                    'id': r.get('.id'),
                    'ext_port': r.get('dst-port', '-'),
                    'protocol': r.get('protocol', 'tcp'),
                    'int_address': r.get('to-addresses', '-'),
                    'int_port': r.get('to-ports', '-'),
                    'packets': r.get('packets', '0'),
                    'comment': r.get('comment', ''),
                    'disabled': r.get('disabled')
                })
    except Exception as e:
        flash(f"Data Loading Error: {e}", "danger")

    return render_template('mikrotik_port_forwarding.html', rules=rules_list)


###########################LOGGGING#############################

@app.route('/mikrotik/logs/rules') 
def system_logs():
    if 'target_ip' not in session: return redirect('/') 

    try:
        api = connect_to_mikrotik() 
        if not api: return redirect(url_for('logout'))

    except Exception as e:
        flash(f"Connection Failed: {e}", "danger")
        return redirect(url_for('mikrotik_gui_main'))

    counts = {'critical': 0, 'error': 0, 'warning': 0, 'info': 0}
    logs_list = []

    try:
        raw_logs = list(api.path('/log').select())
        raw_logs.reverse() 

        for l in raw_logs:
            topics = l.get('topics', '')
            log_type = 'info'
            if 'critical' in topics: 
                log_type = 'critical'; counts['critical'] += 1
            elif 'error' in topics: 
                log_type = 'error'; counts['error'] += 1
            elif 'warning' in topics: 
                log_type = 'warning'; counts['warning'] += 1
            else:
                counts['info'] += 1

            logs_list.append({
                'time': l.get('time', ''),
                'topics': topics,
                'message': l.get('message', ''),
                'type': log_type
            })

    except Exception as e:
        flash(f"Error fetching logs: {e}", "danger")

    return render_template('mikrotik_logs.html', logs=logs_list, counts=counts)

@app.route('/mikrotik/logs/clear')
def clear_logs():
    if 'target_ip' not in session: return redirect('/')
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(session['target_ip'], username=session['target_user'], password=session['target_pass'])
        client.exec_command("/system logging action set memory memory-lines=1; /system logging action set memory memory-lines=1000")
        client.close()
        flash("Logs Cleared!", "success")
    except:
        flash("Failed to clear logs via SSH", "danger")
    return redirect(url_for('system_logs'))

###################### SESSION CLEAR #######################

# @app.before_request
# def check_session():
#     if request.path.startswith('/mikrotik/'):
#         if 'target_ip' not in session:
#             return redirect(url_for('home'))

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, public, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


########################## LOG OUT ##########################
@app.route('/logout')
def logout():
    session.clear() 
    flash("Logged out successfully!", "info")
    return redirect(url_for('home'))

@app.route('/api/system/license')
def verify_system_license():
    try:
        owner_signature = bytes.fromhex(CORE_LICENSE_HASH).decode('utf-8')
        return jsonify({
            "status": "valid",
            "license_type": "Enterprise",
            "integrity_check": "passed",
            "author_ref": owner_signature 
        }), 200
    except Exception:
        return jsonify({"status": "error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)