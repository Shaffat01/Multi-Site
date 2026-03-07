from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from werkzeug.utils import secure_filename
from datetime import datetime
import os

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__)) 

app.secret_key = os.environ.get('SECRET_KEY', 'kloudteck-sm-2026')

db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///kloudteck.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ===================================================
# DATABASE MODELS
# ===================================================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='Viewer') 
    status = db.Column(db.String(20), default='Pending') 

class Portfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bg_image = db.Column(db.String(500), nullable=False)   
    blue_cta = db.Column(db.String(200))                  
    category = db.Column(db.String(100), nullable=False)   
    project_name = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.Text, nullable=False)           
    project_date = db.Column(db.String(100))               
    status = db.Column(db.String(100)) 

class CaseStudy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    bg_image = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text)        
    pdf_url = db.Column(db.String(500))



class Testimonial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(100), nullable=False)
    designation = db.Column(db.String(100), nullable=False)
    quote = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    rating = db.Column(db.Integer, default=5) 

class TeamMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    initials = db.Column(db.String(10))
    position = db.Column(db.String(100), nullable=False)
    skills = db.Column(db.String(200))
    summary = db.Column(db.Text)
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    def get_skills_list(self):
        if self.skills:
            return [s.strip() for s in self.skills.split(',')]
        return []

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    subject = db.Column(db.String(200))
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Unread')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class QuoteRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    solutions = db.Column(db.String(500)) 
    industry = db.Column(db.String(100))
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    company = db.Column(db.String(100))
    budget = db.Column(db.String(100))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

########################## Admin ############################

with app.app_context():
    db.create_all()

    admin_exists = User.query.filter_by(role='Admin').first()
    
    if not admin_exists:
        hashed_password = generate_password_hash('Admin@123', method='pbkdf2:sha256')
        super_admin = User(
            username='admin',
            email='admin@kloudteck.com',
            password=hashed_password,
            role='Admin',
            status='Approved' 
        )
        db.session.add(super_admin)
        db.session.commit()
        print("✅ Super Admin account created successfully!")
        print("Username: admin")
        print("Password: Admin@123")

# ===================================================
# AUTH DECORATORS
# ===================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('⚠️ Please login first!', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'Admin':
            flash('🚫 Access Denied! Admin privileges required.', 'danger')
            return redirect(url_for('admin_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

########################## Register######################################
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('❌ Username or Email already exists!', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('✅ Registration successful! Please wait for Admin approval.', 'info')
        return redirect(url_for('login'))
        
    return render_template('admin/register.html')


########################## Login ######################################

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            if user.status != 'Approved':
                flash('⏳ Your account is pending approval from Admin.', 'warning')
                return redirect(url_for('login'))
            
            session['logged_in'] = True
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash(f'✅ Welcome {user.username}!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('❌ Invalid credentials!', 'danger')
            
    return render_template('admin/login.html')


####################### Notifications ################################
@app.context_processor
def inject_notifications():
    if session.get('logged_in'):
        pending_users = User.query.filter_by(status='Pending').all()
        unread_messages = ContactMessage.query.filter_by(status='Unread').all()
        new_quotes = QuoteRequest.query.order_by(QuoteRequest.id.desc()).limit(5).all()

        notifications = []
        for u in pending_users:
            notifications.append({'icon': 'fa-user-plus', 'color': 'text-teal', 'text': f'New user request: {u.username}', 'link': '/admin/users'})
        
        for m in unread_messages:
            notifications.append({'icon': 'fa-envelope', 'color': 'text-warning', 'text': f'Message from {m.name}', 'link': '/admin/messages'})

        for q in new_quotes:
            notifications.append({'icon': 'fa-file-invoice-dollar', 'color': 'text-info', 'text': f'Quote req from {q.company or q.name}', 'link': '/admin/quotes'})

        return dict(notifications=notifications, noti_count=len(notifications))
    return dict(notifications=[], noti_count=0)


@app.route('/admin/api/notifications')
@login_required
def api_notifications():
    p_users = User.query.filter_by(status='Pending').count()
    u_msgs = ContactMessage.query.filter_by(status='Unread').count()
    total = p_users + u_msgs
    return {'count': total}

########################## User Action ######################################
@app.route('/admin')
@login_required
@admin_only
def admin_dashboard():
    msg_count = ContactMessage.query.count()
    quote_count = QuoteRequest.query.count()
    team_count = TeamMember.query.count()
    user_count = User.query.count()
    recent_messages = ContactMessage.query.order_by(ContactMessage.id.desc()).limit(5).all()
    
    return render_template('admin/admin.html', 
                           username=session.get('username'), 
                           role=session.get('role'),
                           msg_count=msg_count,
                           quote_count=quote_count,
                           team_count=team_count,
                           user_count=user_count,
                           recent_messages=recent_messages)

@app.route('/admin/users')
@login_required
@admin_only
def admin_users():
    all_users = User.query.all()
    return render_template('admin/users.html', 
                           users=all_users, 
                           username=session.get('username'))

@app.route('/admin/create_user', methods=['POST'])
@login_required
@admin_only
def create_user():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role')
    status = request.form.get('status')

    existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing_user:
        flash('❌ Username or Email already exists!', 'danger')
        return redirect(url_for('admin_users'))

    try:
        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username, 
            email=email, 
            password=hashed_password, 
            role=role, 
            status=status
        )
        db.session.add(new_user)
        db.session.commit()
        flash(f'👤 User {username} created successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {str(e)}', 'danger')

    return redirect(url_for('admin_users'))

@app.route('/admin/edit_user/<int:user_id>', methods=['POST'])
@login_required
@admin_only
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    user.username = request.form.get('username')
    user.email = request.form.get('email')
    user.role = request.form.get('role')
    user.status = request.form.get('status')
    
    try:
        db.session.commit()
        flash(f'✅ User {user.username} updated!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {str(e)}', 'danger')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/action/<int:user_id>/<string:action>')
@login_required
@admin_only
def manage_user(user_id, action):
    user = User.query.get_or_404(user_id)
    if action == 'approve': user.status = 'Approved'
    elif action == 'reject': user.status = 'Rejected'
    elif action == 'make_admin': user.role = 'Admin'
    elif action == 'make_editor': user.role = 'Editor'
    elif action == 'delete':
        db.session.delete(user)
        db.session.commit()
        flash(f'🗑️ User deleted!', 'info')
        return redirect(url_for('admin_users'))
    
    db.session.commit()
    flash(f'✅ Action {action} completed!', 'success')
    return redirect(url_for('admin_users'))

######################## Portfolio ###############################

UPLOAD_FOLDER = os.path.join(basedir, 'static/images/portfolio')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 

# os.makedirs(UPLOAD_FOLDER, exist_ok=True)

if not os.path.exists(UPLOAD_FOLDER):
    try:
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    except OSError:
        pass

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/admin/portfolio', methods=['GET', 'POST'])
@login_required
@admin_only
def admin_portfolio():
    if request.method == 'POST':
        p_name = request.form.get('project_name')
        p_category = request.form.get('category')
        p_summary = request.form.get('summary')
        p_blue_cta = request.form.get('blue_cta')
        p_date = request.form.get('project_date')
        p_status = request.form.get('status')
        
        image_url = request.form.get('bg_image_url') 
        file = request.files.get('bg_image_file')

        if file and file.filename != '':
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_url = '/static/images/portfolio/' + filename

        if not image_url:
            flash('❌ Please upload an image or provide a URL!', 'danger')
            return redirect(request.url)
        new_proj = Portfolio(
            project_name=p_name,
            category=p_category,
            summary=p_summary,
            blue_cta=p_blue_cta,
            project_date=p_date,
            status=p_status,
            bg_image=image_url
        )
        db.session.add(new_proj)
        db.session.commit()
        flash('✅ Project Published Successfully!', 'success')
        return redirect(url_for('admin_portfolio'))

    projects = Portfolio.query.order_by(Portfolio.id.desc()).all()
    return render_template('admin/portfolio_mgr.html', projects=projects, username=session.get('username'))

@app.route('/admin/portfolio/edit/<int:id>', methods=['POST'])
@login_required
@admin_only
def edit_portfolio(id):
    proj = Portfolio.query.get_or_404(id)
    
    proj.project_name = request.form.get('project_name')
    proj.category = request.form.get('category')
    proj.summary = request.form.get('summary')
    proj.blue_cta = request.form.get('blue_cta')
    proj.project_date = request.form.get('project_date')
    proj.status = request.form.get('status')
    file = request.files.get('bg_image_file')
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        proj.bg_image = '/static/images/portfolio/' + filename
    elif request.form.get('bg_image_url'):
        proj.bg_image = request.form.get('bg_image_url')

    db.session.commit()
    flash('✅ Project updated successfully!', 'success')
    return redirect(url_for('admin_portfolio'))

@app.route('/admin/portfolio/delete/<int:id>')
@login_required
@admin_only
def delete_portfolio(id):
    proj = Portfolio.query.get_or_404(id)
    db.session.delete(proj)
    db.session.commit()
    flash('🗑️ Project removed from portfolio.', 'info')
    return redirect(url_for('admin_portfolio'))

######################## Case Studies ##########################

# CASE_IMAGE_FOLDER = 'static/images/cases/images'
# CASE_PDF_FOLDER = 'static/images/cases/pdfs'
# os.makedirs(CASE_IMAGE_FOLDER, exist_ok=True)
# os.makedirs(CASE_PDF_FOLDER, exist_ok=True)

CASE_IMAGE_FOLDER_REL = 'static/images/cases/images' 
CASE_PDF_FOLDER_REL = 'static/images/cases/pdfs'

CASE_IMAGE_FOLDER = os.path.join(basedir, CASE_IMAGE_FOLDER_REL) 
CASE_PDF_FOLDER = os.path.join(basedir, CASE_PDF_FOLDER_REL)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CASE_IMAGE_FOLDER, exist_ok=True)
os.makedirs(CASE_PDF_FOLDER, exist_ok=True)


if 'VERCEL' not in os.environ:
    os.makedirs(CASE_IMAGE_FOLDER, exist_ok=True)
    os.makedirs(CASE_PDF_FOLDER, exist_ok=True)
else:
    print("Running on Vercel: Skipping directory creation.")


@app.route('/admin/case-studies', methods=['GET', 'POST'])
@login_required
@admin_only
def admin_case_studies():
    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        content = request.form.get('content')      
        img_file = request.files.get('bg_image')
        pdf_file = request.files.get('pdf_file')
        img_path = request.form.get('bg_image_url') or ""
        pdf_path = ""

        # Image upload
        if img_file and img_file.filename != '':
            img_filename = secure_filename(img_file.filename)
            img_file.save(os.path.join(CASE_IMAGE_FOLDER, img_filename))
            img_path = f'/{CASE_IMAGE_FOLDER}/{img_filename}'

        # PDF upload
        if pdf_file and pdf_file.filename != '':
            pdf_filename = secure_filename(pdf_file.filename)
            pdf_file.save(os.path.join(CASE_PDF_FOLDER, pdf_filename))
            pdf_path = f'/{CASE_PDF_FOLDER}/{pdf_filename}'

        if not img_path:
            flash('❌ Please upload an image or provide URL!', 'danger')
            return redirect(url_for('admin_case_studies'))

        new_case = CaseStudy(
            title=title,
            category=category,
            content=content,
            bg_image=img_path,
            pdf_url=pdf_path
        )
        db.session.add(new_case)
        db.session.commit()
        flash('✅ Case Study Published Successfully!', 'success')
        return redirect(url_for('admin_case_studies'))

    studies = CaseStudy.query.order_by(CaseStudy.id.desc()).all()
    return render_template('admin/case_mgr.html',
                           studies=studies,
                           username=session.get('username'),
                           role=session.get('role'))


@app.route('/admin/case-studies/edit/<int:id>', methods=['POST'])
@login_required
@admin_only
def edit_case(id):
    case = CaseStudy.query.get_or_404(id)
    case.title = request.form.get('title')
    case.category = request.form.get('category')
    case.content = request.form.get('content')  

    img_file = request.files.get('bg_image')
    if img_file and img_file.filename != '':
        img_filename = secure_filename(img_file.filename)
        img_file.save(os.path.join(CASE_IMAGE_FOLDER, img_filename))
        case.bg_image = f'/{CASE_IMAGE_FOLDER}/{img_filename}'
    elif request.form.get('bg_image_url'):
        case.bg_image = request.form.get('bg_image_url')

    pdf_file = request.files.get('pdf_file')
    if pdf_file and pdf_file.filename != '':
        pdf_filename = secure_filename(pdf_file.filename)
        pdf_file.save(os.path.join(CASE_PDF_FOLDER, pdf_filename))
        case.pdf_url = f'/{CASE_PDF_FOLDER}/{pdf_filename}'

    db.session.commit()
    flash('✅ Case Study Updated Successfully!', 'success')
    return redirect(url_for('admin_case_studies'))


@app.route('/admin/case-studies/delete/<int:id>')
@login_required
@admin_only
def delete_case(id):
    case = CaseStudy.query.get_or_404(id)
    db.session.delete(case)
    db.session.commit()
    flash('🗑️ Case Study Removed.', 'info')
    return redirect(url_for('admin_case_studies'))

####################### Cases testimonials ############################################

@app.route('/admin/testimonial')
@login_required
@admin_only
def admin_testimonials():
    all_testimonials = Testimonial.query.order_by(Testimonial.id.desc()).all()
    return render_template('admin/testimonials_mgr.html', 
                           testimonials=all_testimonials, 
                           username=session.get('username'),
                           role=session.get('role'))

@app.route('/admin/testimonial/create', methods=['POST'])
@login_required
@admin_only
def create_testimonial():
    author = request.form.get('author')
    designation = request.form.get('designation')
    quote = request.form.get('quote')
    category = request.form.get('category')
    rating = request.form.get('rating', default=5, type=int)
    
    try:
        new_testi = Testimonial(
            author=author, 
            designation=designation, 
            quote=quote, 
            category=category,
            rating=rating 
        )
        db.session.add(new_testi)
        db.session.commit()
        flash('✅ Client feedback added successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {str(e)}', 'danger')
        
    return redirect(url_for('admin_testimonials'))

@app.route('/admin/testimonial/edit/<int:id>', methods=['POST'])
@login_required
@admin_only
def edit_testimonial(id):
    testi = Testimonial.query.get_or_404(id)
    testi.author = request.form.get('author')
    testi.designation = request.form.get('designation')
    testi.quote = request.form.get('quote')
    testi.category = request.form.get('category')
    # রেটিং আপডেট করা
    testi.rating = request.form.get('rating', type=int)
    
    try:
        db.session.commit()
        flash('✅ Testimonial updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {str(e)}', 'danger')
        
    return redirect(url_for('admin_testimonials'))

@app.route('/admin/testimonial/delete/<int:id>')
@login_required
@admin_only
def delete_testimonial(id):
    testi = Testimonial.query.get_or_404(id)
    try:
        db.session.delete(testi)
        db.session.commit()
        flash('🗑️ Testimonial deleted.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {str(e)}', 'danger')
        
    return redirect(url_for('admin_testimonials'))


######################## About ##############

@app.route('/about')
def about():
    active_members = TeamMember.query.filter_by(is_active=True).order_by(TeamMember.display_order.asc()).all()
    return render_template('about.html', members=active_members)

@app.route('/admin/team')
@login_required
@admin_only
def admin_team():
    members = TeamMember.query.order_by(TeamMember.display_order.asc()).all()
    return render_template('admin/team_members.html', members=members)

@app.route('/admin/team/add', methods=['POST'])
def admin_team_add():
    new_member = TeamMember(
        name=request.form.get('name'),
        initials=request.form.get('initials'), # initials রিসিভ করা
        position=request.form.get('position'),
        skills=request.form.get('skills'),
        summary=request.form.get('summary'),
        is_active=True if request.form.get('is_active') else False
    )
    db.session.add(new_member)
    db.session.commit()
    return redirect(url_for('admin_team'))

# --- Edit Member Route আপডেট ---
@app.route('/admin/team/edit/<int:member_id>', methods=['POST'])
def admin_team_edit(member_id):
    member = TeamMember.query.get_or_404(member_id)
    member.name = request.form.get('name')
    member.initials = request.form.get('initials') # initials আপডেট করা
    member.position = request.form.get('position')
    member.skills = request.form.get('skills')
    member.summary = request.form.get('summary')
    member.display_order = request.form.get('display_order')
    member.is_active = True if request.form.get('is_active') else False
    
    db.session.commit()
    return redirect(url_for('admin_team'))

@app.route('/admin/team/delete/<int:member_id>', methods=['POST'])
def admin_team_delete(member_id):
    member = TeamMember.query.get_or_404(member_id)
    try:
        db.session.delete(member)
        db.session.commit()
        flash('Member deleted!', 'warning')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        
    return redirect(url_for('admin_team'))

######################### Contact form filling ##################
@app.route('/admin/messages')
@login_required
@admin_only
def admin_messages():
    messages = ContactMessage.query.order_by(ContactMessage.id.desc()).all()
    return render_template('admin/messages.html', messages=messages, username=session.get('username'))

@app.route('/admin/messages/delete/<int:id>')
@login_required
@admin_only
def delete_message(id):
    msg = ContactMessage.query.get_or_404(id)
    db.session.delete(msg)
    db.session.commit()
    flash('🗑️ Message deleted.', 'info')
    return redirect(url_for('admin_messages'))


#################### Quote ###################

@app.route('/submit-quote', methods=['POST'])
def submit_quote():
    if request.method == 'POST':
        solutions_list = request.form.getlist('solutions')
        solutions = ", ".join(solutions_list)
        new_quote = QuoteRequest(
            solutions=solutions,
            industry=request.form.get('industry'),
            name=request.form.get('name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            company=request.form.get('company'),
            budget=request.form.get('budget'),
            details=request.form.get('details')
        )
        
        try:
            db.session.add(new_quote)
            db.session.commit()
            flash('✅ Quote request submitted! Our team will contact you within 24 hours.', 'success')
        except Exception as e:
            db.session.rollback()
            flash('❌ Error: Could not submit request.', 'danger')
            
        return redirect(url_for('quote'))

@app.route('/admin/quotes')
@login_required
@admin_only
def admin_quotes():
    all_quotes = QuoteRequest.query.order_by(QuoteRequest.id.desc()).all()
    return render_template('admin/quotes.html', quotes=all_quotes, username=session.get('username'))

@app.route('/admin/quote/delete/<int:id>')
@login_required
@admin_only
def delete_quote(id):
    quote = QuoteRequest.query.get_or_404(id)
    db.session.delete(quote)
    db.session.commit()
    flash('🗑️ Quote request deleted.', 'info')
    return redirect(url_for('admin_quotes'))



#################### PAGES ################################

@app.route('/')
def index():
    all_testimonials = Testimonial.query.all()
    return render_template('index.html', testimonials=all_testimonials)


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        subject = request.form.get('subject')
        message = request.form.get('message')

        try:
            new_msg = ContactMessage(
                name=name, email=email, phone=phone, 
                subject=subject, message=message
            )
            db.session.add(new_msg)
            db.session.commit()
            flash('✅ Message sent! We will contact you soon.', 'success')
        except Exception as e:
            db.session.rollback()
            flash('❌ Something went wrong. Please try again.', 'danger')
        return redirect(url_for('contact'))
    testimonials = Testimonial.query.all()
    return render_template('contact.html', testimonials=testimonials)

@app.route('/support')
def support():
    return render_template('support.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/portfolio')
def portfolio():
    all_projects = Portfolio.query.order_by(Portfolio.id.desc()).all()
    return render_template('portfolio.html', projects=all_projects)

@app.route('/case-studies')
def case_studies():
    all_studies = CaseStudy.query.all()
    all_testimonials = Testimonial.query.all()
    return render_template('case-studies.html', studies=all_studies, testimonials=all_testimonials)

##################### SOLUTIONS ############################

@app.route('/solutions')
def solutions_all():
    return render_template('services/solutions-index.html')

@app.route('/services/managed-network-wifi-solutions')
def managed_network():
    return render_template('services/managed-network-wifi-solutions.html')

@app.route('/services/commercial-access-control-systems')
def access_control():
    return render_template('services/commercial-access-control-systems.html')

@app.route('/services/commercial-cctv-surveillance')
def cctv():
    return render_template('services/commercial-cctv-surveillance.html')

@app.route('/services/structured-cabling-fiber-installation')
def structured_cabling():
    return render_template('services/structured-cabling-fiber-installation.html')

@app.route('/services/business-voip-phone-systems')
def business_phone():
    return render_template('services/business-voip-phone-systems.html')

@app.route('/services/commercial-tv-digital-display-solutions')
def tv_display():
    return render_template('services/commercial-tv-digital-display-solutions.html')


@app.route('/services/full-stack-web-development')
def web_dev():
    return render_template('services/web-dev.html')

@app.route('/services/mikrotik-device-orchestration')
def mikrotik_orchestration():
    return render_template('services/mikrotik.html')

@app.route('/services/network-monitoring-log-servers')
def network_monitoring():
    return render_template('services/monitoring.html')

@app.route('/services/ipbx-phone-systems')
def ipbx_systems():
    return render_template('services/ipbx.html')

############### INDUSRIES ##############################################

@app.route('/industries')
def industries_all():
    return render_template('industries/industries-index.html')

@app.route('/industries/commercial-office')
def industry_office():
    return render_template('industries/commercial-office.html')

@app.route('/industries/hospitality')
def industry_hospitality():
    return render_template('industries/hospitality.html')

@app.route('/industries/warehouses-distribution')
def industry_warehouse():
    return render_template('industries/warehouses-distribution.html')

@app.route('/industries/multi-family-communities')
def industry_multifamily():
    return render_template('industries/multi-family-communities.html')

@app.route('/industries/retail')
def industry_retail():
    return render_template('industries/retail.html')


# @app.route('/case-studies')
# def case_studies():
#     all_studies = CaseStudy.query.all()
#     return render_template('case-studies.html', studies=all_studies)

@app.route("/quote", methods=['GET', 'POST'])
def quote():
    if request.method == 'POST':
        solutions_list = request.form.getlist('solutions')
        solutions = ", ".join(solutions_list)
        
        industry = request.form.get('industry')
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        company = request.form.get('company')
        budget = request.form.get('budget')
        details = request.form.get('details')

        try:
            new_quote = QuoteRequest(
                solutions=solutions, industry=industry, name=name,
                email=email, phone=phone, company=company,
                budget=budget, details=details
            )
            db.session.add(new_quote)
            db.session.commit()
            flash('✅ Quote request submitted successfully! We will contact you soon.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error: {str(e)}', 'danger')

        return redirect(url_for('quote'))
    return render_template('quote.html')



# @app.route('/managed-network-wifi-solutions')
# def managed_network():
#     return render_template('managed-network-wifi.html')

@app.route('/admin/logout')
def logout():
    session.clear()
    flash('🔒 Logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)