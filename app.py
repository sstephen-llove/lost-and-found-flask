from flask import Flask, render_template, request, redirect, url_for, session
import os
import sqlite3
from werkzeug.utils import secure_filename

# --- Flask setup ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- Secret Key for Sessions ---
app.secret_key = "supersecurepassword123"  # change this later!

# --- Database Setup ---
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()

    # Add item columns if missing
    try:
        conn.execute("ALTER TABLE items ADD COLUMN is_claimed INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Add claim status column if missing
    try:
        conn.execute("ALTER TABLE claims ADD COLUMN status TEXT DEFAULT 'pending'")
    except sqlite3.OperationalError:
        pass

    # Ensure tables exist
    conn.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            location TEXT,
            date_found TEXT,
            photo TEXT,
            approved INTEGER DEFAULT 0,
            is_claimed INTEGER DEFAULT 0
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            claimant_name TEXT,
            email TEXT,
            message TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Database tables ensured.")

# --- Routes ---

@app.route('/')
def home():
    q = request.args.get('q', '').strip()

    conn = get_db_connection()

    # Only show approved items (and optionally hide claimed items)
    base_query = """
        SELECT id, name, description, location, date_found, photo
        FROM items
        WHERE approved = 1
    """
    params = []

    # If you want claimed items to disappear from home, uncomment:
    # base_query += " AND is_claimed = 0"

    if q:
        base_query += """
            AND (
                name LIKE ?
                OR description LIKE ?
                OR location LIKE ?
            )
        """
        like = f"%{q}%"
        params.extend([like, like, like])

    base_query += " ORDER BY id DESC"

    items = conn.execute(base_query, params).fetchall()
    conn.close()

    return render_template('home.html', items=items, q=q)

@app.route('/report', methods=['GET', 'POST'])
def report():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        location = request.form['location']
        date_found = request.form['date_found']
        photo = request.files.get('photo')

        filename = ""
        if photo and photo.filename:
            filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO items (name, description, location, date_found, photo, approved) VALUES (?, ?, ?, ?, ?, 0)',
            (name, description, location, date_found, filename)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('home'))

    return render_template('report.html')

@app.route('/claim/<int:item_id>', methods=['GET', 'POST'])
def claim(item_id):
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id=? AND approved=1', (item_id,)).fetchone()
    if not item:
        conn.close()
        return "Item not found or not approved.", 404

    if request.method == 'POST':
        claimant_name = request.form['claimant_name']
        email = request.form['email']
        message = request.form['message']

        conn.execute(
            'INSERT INTO claims (item_id, claimant_name, email, message) VALUES (?, ?, ?, ?)',
            (item_id, claimant_name, email, message)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('home'))

    conn.close()
    return render_template('claim.html', item=item)

# --- Admin Login ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form['password']
        if password == 'admin123':  # change this for real use
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error="Incorrect password.")
    return render_template('admin_login.html')

# --- Admin Logout ---
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('home'))

# --- Admin Dashboard ---
@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    items = conn.execute('SELECT * FROM items ORDER BY id DESC').fetchall()
    claims = conn.execute('SELECT * FROM claims ORDER BY id DESC').fetchall()
    conn.close()

    claims_by_item = {}
    for c in claims:
        claims_by_item.setdefault(c['item_id'], []).append(c)

    return render_template('admin_dashboard.html', items=items, claims_by_item=claims_by_item)

# --- Approve Item ---
@app.route('/admin/approve/<int:item_id>')
def approve_item(item_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    conn.execute('UPDATE items SET approved=1 WHERE id=?', (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

# --- Disapprove Item ---
@app.route('/admin/disapprove/<int:item_id>')
def disapprove_item(item_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    conn.execute('UPDATE items SET approved=0 WHERE id=?', (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

# --- Delete Item ---
@app.route('/admin/delete/<int:item_id>')
def delete_item(item_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    conn.execute('DELETE FROM items WHERE id=?', (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
