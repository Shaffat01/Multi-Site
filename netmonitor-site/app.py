import os
import csv
import io
import logging
from datetime import datetime
from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, flash
)
from flask_apscheduler import APScheduler
from config import Config
from models import db, Node
from monitor import monitor

# Disable Flask access logs (cleaner output)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize extensions
db.init_app(app)

# ============ FIX: Only initialize scheduler ONCE ============
# When Flask debug=True, the app starts twice. We need to detect this.
def is_main_process():
    """Check if this is the main Werkzeug process (not the reloader)."""
    return os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug


# Initialize monitor only in main process
if is_main_process():
    monitor.init_app(app)


# Setup scheduler ONLY in main process
scheduler = APScheduler()


@scheduler.task(
    'interval',
    id='monitor_nodes',
    seconds=Config.PING_INTERVAL,
    misfire_grace_time=30,
    max_instances=1,
    coalesce=True
)
def scheduled_monitor():
    """Scheduled job to monitor all nodes."""
    with app.app_context():
        monitor.monitor_all_nodes()


# Create tables
with app.app_context():
    db.create_all()


# Start scheduler only in main process
if is_main_process():
    scheduler.init_app(app)
    scheduler.start()
    
    # Initial ping at startup
    import threading
    def initial_ping():
        import time
        time.sleep(3)
        print("[STARTUP] Running initial ping cycle...")
        with app.app_context():
            monitor.monitor_all_nodes()
    
    threading.Thread(target=initial_ping, daemon=True).start()


# ============ WEB ROUTES ============

@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html')


@app.route('/add', methods=['GET', 'POST'])
def add_node():
    """Add a new node."""
    if request.method == 'POST':
        node_name = request.form.get('node_name', '').strip()
        ip_address = request.form.get('ip_address', '').strip()

        if not node_name or not ip_address:
            flash('Node name and IP address are required.', 'error')
            return render_template('add_node.html')

        existing = Node.query.filter_by(ip_address=ip_address).first()
        if existing:
            flash(f'A node with IP {ip_address} already exists.', 'error')
            return render_template('add_node.html')

        node = Node(
            node_name=node_name,
            ip_address=ip_address,
            status='Unknown',
            last_status_change=datetime.utcnow()
        )
        db.session.add(node)
        db.session.commit()

        import threading
        t = threading.Thread(target=monitor.ping_single_node, args=(node.id,))
        t.daemon = True
        t.start()

        flash(f'Node "{node_name}" added successfully.', 'success')
        return redirect(url_for('index'))

    return render_template('add_node.html')


@app.route('/edit/<int:node_id>', methods=['GET', 'POST'])
def edit_node(node_id):
    """Edit an existing node."""
    node = db.session.get(Node, node_id)
    if not node:
        flash('Node not found.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        node_name = request.form.get('node_name', '').strip()
        ip_address = request.form.get('ip_address', '').strip()
        enabled = request.form.get('enabled') == 'on'

        if not node_name or not ip_address:
            flash('Node name and IP address are required.', 'error')
            return render_template('edit_node.html', node=node)

        existing = Node.query.filter(
            Node.ip_address == ip_address,
            Node.id != node_id
        ).first()
        if existing:
            flash(f'Another node with IP {ip_address} already exists.', 'error')
            return render_template('edit_node.html', node=node)

        node.node_name = node_name
        node.ip_address = ip_address
        node.enabled = enabled
        node.updated_at = datetime.utcnow()
        db.session.commit()

        flash(f'Node "{node_name}" updated successfully.', 'success')
        return redirect(url_for('index'))

    return render_template('edit_node.html', node=node)


@app.route('/delete/<int:node_id>', methods=['POST'])
def delete_node(node_id):
    """Delete a node."""
    node = db.session.get(Node, node_id)
    if not node:
        flash('Node not found.', 'error')
        return redirect(url_for('index'))

    node_name = node.node_name
    db.session.delete(node)
    db.session.commit()
    flash(f'Node "{node_name}" deleted successfully.', 'success')
    return redirect(url_for('index'))


@app.route('/upload', methods=['GET', 'POST'])
def upload_csv():
    """Upload nodes from CSV file."""
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('No file selected.', 'error')
            return render_template('upload_csv.html')

        file = request.files['csv_file']
        if file.filename == '':
            flash('No file selected.', 'error')
            return render_template('upload_csv.html')

        if not file.filename.endswith('.csv'):
            flash('Please upload a CSV file.', 'error')
            return render_template('upload_csv.html')

        try:
            stream = io.StringIO(file.stream.read().decode('utf-8-sig'))
            reader = csv.DictReader(stream)

            added = 0
            skipped = 0
            errors = []

            for row_num, row in enumerate(reader, start=2):
                node_name = (
                    row.get('node_name') or row.get('Node') or
                    row.get('node') or row.get('hostname') or
                    row.get('Hostname') or row.get('Name') or ''
                ).strip()

                ip_address = (
                    row.get('ip_address') or row.get('IP Address') or
                    row.get('ip') or row.get('IP') or
                    row.get('address') or ''
                ).strip()

                if not node_name or not ip_address:
                    errors.append(f"Row {row_num}: Missing node name or IP address")
                    skipped += 1
                    continue

                existing = Node.query.filter_by(ip_address=ip_address).first()
                if existing:
                    skipped += 1
                    continue

                node = Node(
                    node_name=node_name,
                    ip_address=ip_address,
                    status='Unknown',
                    last_status_change=datetime.utcnow()
                )
                db.session.add(node)
                added += 1

            db.session.commit()

            msg = f'Successfully added {added} nodes. Skipped {skipped} (duplicates/errors).'
            if errors:
                msg += f' Errors: {"; ".join(errors[:5])}'
            flash(msg, 'success' if added > 0 else 'warning')

            import threading
            t = threading.Thread(target=monitor.monitor_all_nodes)
            t.daemon = True
            t.start()

            return redirect(url_for('index'))

        except Exception as e:
            flash(f'Error processing CSV: {str(e)}', 'error')
            return render_template('upload_csv.html')

    return render_template('upload_csv.html')


# ============ API ROUTES ============

@app.route('/api/nodes')
def api_get_nodes():
    """API endpoint to get all nodes with sorting."""
    sort_by = request.args.get('sort', 'since_last_change')
    order = request.args.get('order', 'asc')

    sort_map = {
        'node_name': Node.node_name,
        'ip_address': Node.ip_address,
        'response_time': Node.response_time,
        'packet_loss': Node.packet_loss,
        'status': Node.status,
        'last_status_change': Node.last_status_change,
        'since_last_change': Node.last_status_change
    }

    sort_column = sort_map.get(sort_by, Node.last_status_change)

    if sort_by == 'since_last_change':
        if order == 'asc':
            nodes = Node.query.order_by(sort_column.desc()).all()
        else:
            nodes = Node.query.order_by(sort_column.asc()).all()
    else:
        if order == 'desc':
            nodes = Node.query.order_by(sort_column.desc()).all()
        else:
            nodes = Node.query.order_by(sort_column.asc()).all()

    return jsonify({
        'nodes': [node.to_dict() for node in nodes],
        'total': len(nodes),
        'sort': sort_by,
        'order': order
    })

@app.route('/maker')
def maker():
    return """
    <html>
    <body style="font-family: Arial; padding: 40px;">
        <h2>👨‍💻 App Maker</h2>
        <h3>Name: Shaffat Mahmud</h3>
        <h3>Email: shaffa3x@gmail.com</h3>
    </body>
    </html>
    """

@app.route('/api/nodes/<int:node_id>/ping', methods=['POST'])
def api_ping_node(node_id):
    """Manually trigger ping for a single node."""
    node = db.session.get(Node, node_id)
    if not node:
        return jsonify({'error': 'Node not found'}), 404

    monitor.ping_single_node(node_id)
    db.session.refresh(node)
    return jsonify(node.to_dict())


@app.route('/api/nodes/delete', methods=['POST'])
def api_delete_node():
    """Delete node via API."""
    data = request.get_json()
    node_id = data.get('node_id')

    node = db.session.get(Node, node_id)
    if not node:
        return jsonify({'error': 'Node not found'}), 404

    db.session.delete(node)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/refresh', methods=['POST'])
def api_refresh_all():
    """Trigger manual refresh of all nodes."""
    import threading
    t = threading.Thread(target=monitor.monitor_all_nodes)
    t.daemon = True
    t.start()
    return jsonify({'success': True, 'message': 'Refresh started'})


@app.route('/api/stats')
def api_stats():
    """Get summary statistics."""
    total = Node.query.count()
    up = Node.query.filter_by(status='Node Up').count()
    down = Node.query.filter_by(status='Node Down').count()
    warning = Node.query.filter_by(status='Warning').count()
    unknown = Node.query.filter_by(status='Unknown').count()

    return jsonify({
        'total': total,
        'up': up,
        'down': down,
        'warning': warning,
        'unknown': unknown
    })


if __name__ == '__main__':
    # IMPORTANT: debug=False to prevent double scheduler instance
    # Use use_reloader=False if you need debug=True
    app.run(
        debug=False,           # Changed to False
        host='0.0.0.0',
        port=3000,
        use_reloader=False     # Prevents double scheduler
    )
