import os
import csv
import io
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, send_file, jsonify)
from flask_login import (LoginManager, login_user, login_required,
                         logout_user, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from models import db, User, Expense, Category, Budget

# ─────────────────────────────────────────
#  App config
# ─────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY']                  = 'mysecretkey'
app.config['SQLALCHEMY_DATABASE_URI']     = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Receipt uploads
app.config['UPLOAD_FOLDER']  = os.path.join('static', 'receipts')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024   # 5 MB max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)

# ─────────────────────────────────────────
#  Login manager
# ─────────────────────────────────────────
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ─────────────────────────────────────────
#  Helper: allowed file check
# ─────────────────────────────────────────
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ─────────────────────────────────────────
#  Home
# ─────────────────────────────────────────
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# ─────────────────────────────────────────
#  Auth — Register / Login / Logout
# ─────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username        = request.form['username']
        password        = request.form['password']
        hashed_password = generate_password_hash(password)
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
        else:
            new_user = User(username=username, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user     = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# ─────────────────────────────────────────
#  Dashboard
# ─────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    now      = datetime.now()
    expenses = Expense.query.filter_by(user_id=current_user.id).all()

    category_totals = {}
    for expense in expenses:
        cname = expense.category.name if expense.category else 'Uncategorized'
        category_totals[cname] = category_totals.get(cname, 0) + expense.amount

    # Budget warnings
    budgets       = Budget.query.filter_by(user_id=current_user.id,
                                            month=now.month, year=now.year).all()
    budget_warnings = []
    for budget in budgets:
        spent = db.session.query(db.func.sum(Expense.amount)).filter(
            Expense.user_id     == current_user.id,
            Expense.category_id == budget.category_id,
            Expense.date.like(f'{now.year}-{str(now.month).zfill(2)}%')
        ).scalar() or 0
        pct = (spent / budget.amount * 100) if budget.amount > 0 else 0
        if pct >= 80:
            budget_warnings.append({
                'category': budget.category.name, 'spent': spent,
                'limit': budget.amount, 'percentage': pct,
                'over': spent > budget.amount
            })

    suggestions = []
    if category_totals:
        top = max(category_totals, key=category_totals.get)
        if category_totals[top] > 3000:
            suggestions.append(
                f'You spent ${category_totals[top]:.2f} on {top}. Consider reviewing.')
        else:
            suggestions.append('Your spending is within a reasonable range. Keep it up!')

    return render_template('dashboard.html',
                           username        = current_user.username,
                           expenses        = expenses,
                           categories      = list(category_totals.keys()),
                           totals          = list(category_totals.values()),
                           suggestions     = suggestions,
                           budget_warnings = budget_warnings,
                           currency        = current_user.currency)

# ─────────────────────────────────────────
#  Expenses — CRUD
# ─────────────────────────────────────────
@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    categories = Category.query.all()
    if request.method == 'POST':
        title       = request.form['title']
        amount      = float(request.form['amount'])
        date        = request.form['date']
        category_id = request.form['category']
        upi_ref     = request.form.get('upi_ref', '').strip()
        notes       = request.form.get('notes', '').strip()
        is_recurring = 'is_recurring' in request.form

        # Handle receipt upload
        receipt_path = None
        file = request.files.get('receipt')
        if file and file.filename and allowed_file(file.filename):
            filename     = secure_filename(
                f"{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            save_path    = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(save_path)
            receipt_path = filename   # store just the filename

        new_expense = Expense(
            title       = title,
            amount      = amount,
            date        = date,
            user_id     = current_user.id,
            category_id = category_id,
            upi_ref     = upi_ref or None,
            notes       = notes or None,
            is_recurring = is_recurring,
            receipt     = receipt_path
        )
        db.session.add(new_expense)
        db.session.commit()
        flash('Expense added!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_expense.html', categories=categories)


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_expense(id):
    expense    = db.get_or_404(Expense, id)
    if expense.user_id != current_user.id:
        flash('Not authorized.', 'error')
        return redirect(url_for('dashboard'))
    categories = Category.query.all()
    if request.method == 'POST':
        expense.title       = request.form['title']
        expense.amount      = float(request.form['amount'])
        expense.date        = request.form['date']
        expense.category_id = request.form['category']
        expense.upi_ref     = request.form.get('upi_ref', '').strip() or None
        expense.notes       = request.form.get('notes', '').strip() or None
        expense.is_recurring = 'is_recurring' in request.form

        # Replace receipt if new file uploaded
        file = request.files.get('receipt')
        if file and file.filename and allowed_file(file.filename):
            # Delete old file if exists
            if expense.receipt:
                old = os.path.join(app.config['UPLOAD_FOLDER'], expense.receipt)
                if os.path.exists(old):
                    os.remove(old)
            filename        = secure_filename(
                f"{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            expense.receipt = filename

        db.session.commit()
        flash('Expense updated!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('edit_expense.html', expense=expense, categories=categories)


@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_expense(id):
    expense = db.get_or_404(Expense, id)
    if expense.user_id != current_user.id:
        flash('Not authorized.', 'error')
        return redirect(url_for('dashboard'))
    # Delete receipt file too
    if expense.receipt:
        path = os.path.join(app.config['UPLOAD_FOLDER'], expense.receipt)
        if os.path.exists(path):
            os.remove(path)
    db.session.delete(expense)
    db.session.commit()
    flash('Expense deleted!', 'success')
    return redirect(url_for('dashboard'))

# ─────────────────────────────────────────
#  Export to CSV  ← NEW
# ─────────────────────────────────────────
@app.route('/export/csv')
@login_required
def export_csv():
    expenses = Expense.query.filter_by(user_id=current_user.id)\
                            .order_by(Expense.date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow(['Date', 'Title', 'Category', 'Amount',
                     'UPI Ref', 'Notes', 'Recurring'])

    # Data rows
    for e in expenses:
        writer.writerow([
            e.date,
            e.title,
            e.category.name if e.category else 'Uncategorized',
            f'{e.amount:.2f}',
            e.upi_ref   or '',
            e.notes     or '',
            'Yes' if e.is_recurring else 'No'
        ])

    output.seek(0)
    filename = f"fintracker_{current_user.username}_{datetime.now().strftime('%Y%m')}.csv"

    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype   = 'text/csv',
        as_attachment = True,
        download_name = filename
    )

# ─────────────────────────────────────────
#  Monthly Summary  ← NEW
# ─────────────────────────────────────────
@app.route('/summary')
@login_required
def monthly_summary():
    expenses = Expense.query.filter_by(user_id=current_user.id).all()

    # Group by YYYY-MM
    monthly = {}
    for e in expenses:
        key = e.date[:7]   # "2026-05"
        monthly[key] = monthly.get(key, 0) + e.amount

    # Sort by date descending
    sorted_months = sorted(monthly.items(), reverse=True)

    # Build richer data: month label, total, vs previous month
    summary_data = []
    keys = [m[0] for m in sorted_months]
    for i, (key, total) in enumerate(sorted_months):
        prev_total = sorted_months[i + 1][1] if i + 1 < len(sorted_months) else None
        if prev_total:
            change_pct = ((total - prev_total) / prev_total) * 100
        else:
            change_pct = None

        # Parse month label: "2026-05" → "May 2026"
        dt    = datetime.strptime(key, '%Y-%m')
        label = dt.strftime('%B %Y')

        summary_data.append({
            'key'        : key,
            'label'      : label,
            'total'      : total,
            'change_pct' : change_pct,
            'up'         : change_pct > 0 if change_pct is not None else None
        })

    # Month labels and totals for chart (chronological order)
    chart_labels = [d['label'] for d in reversed(summary_data)]
    chart_totals = [d['total'] for d in reversed(summary_data)]

    return render_template('monthly_summary.html',
                           summary_data  = summary_data,
                           chart_labels  = chart_labels,
                           chart_totals  = chart_totals,
                           currency      = current_user.currency)

# ─────────────────────────────────────────
#  Settings  ← NEW
# ─────────────────────────────────────────
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        action = request.form.get('action')

        # ── Change username ──
        if action == 'username':
            new_username = request.form['username'].strip()
            if not new_username:
                flash('Username cannot be empty.', 'error')
            elif User.query.filter_by(username=new_username).first():
                flash('That username is already taken.', 'error')
            else:
                current_user.username = new_username
                db.session.commit()
                flash('Username updated!', 'success')

        # ── Change password ──
        elif action == 'password':
            current_pw  = request.form['current_password']
            new_pw      = request.form['new_password']
            confirm_pw  = request.form['confirm_password']
            if not check_password_hash(current_user.password, current_pw):
                flash('Current password is wrong.', 'error')
            elif new_pw != confirm_pw:
                flash('New passwords do not match.', 'error')
            elif len(new_pw) < 6:
                flash('Password must be at least 6 characters.', 'error')
            else:
                current_user.password = generate_password_hash(new_pw)
                db.session.commit()
                flash('Password changed!', 'success')

        # ── Change currency symbol ──
        elif action == 'currency':
            currency = request.form['currency'].strip()
            if currency:
                current_user.currency = currency
                db.session.commit()
                flash('Currency updated!', 'success')

        # ── Toggle theme ──
        elif action == 'theme':
            theme = request.form.get('theme', 'light')
            current_user.theme = theme
            db.session.commit()
            return jsonify({'status': 'ok', 'theme': theme})

        return redirect(url_for('settings'))

    return render_template('settings.html', user=current_user)

# ─────────────────────────────────────────
#  UPI Reference Log  ← NEW (realistic version)
# ─────────────────────────────────────────
# This route lets a user log an expense directly from a UPI
# transaction reference number (like from PhonePe/GPay notification)
@app.route('/upi/log', methods=['GET', 'POST'])
@login_required
def upi_log():
    categories = Category.query.all()
    if request.method == 'POST':
        upi_ref     = request.form['upi_ref'].strip()
        amount      = float(request.form['amount'])
        title       = request.form['title'].strip()
        category_id = request.form['category']
        date        = request.form.get('date') or datetime.now().strftime('%Y-%m-%d')

        # Check duplicate UPI ref for this user
        duplicate = Expense.query.filter_by(
            user_id = current_user.id,
            upi_ref = upi_ref
        ).first()

        if duplicate:
            flash(f'UPI ref {upi_ref} already logged!', 'error')
        else:
            expense = Expense(
                title       = title,
                amount      = amount,
                date        = date,
                user_id     = current_user.id,
                category_id = category_id,
                upi_ref     = upi_ref
            )
            db.session.add(expense)
            db.session.commit()
            flash(f'UPI transaction {upi_ref} logged!', 'success')
            return redirect(url_for('dashboard'))

    return render_template('upi_log.html', categories=categories,
                           today=datetime.now().strftime('%Y-%m-%d'))

# ─────────────────────────────────────────
#  Categories — CRUD
# ─────────────────────────────────────────
@app.route('/categories')
@login_required
def list_categories():
    categories = Category.query.all()
    return render_template('categories.html', categories=categories)

@app.route('/categories/add', methods=['GET', 'POST'])
@login_required
def add_category():
    if request.method == 'POST':
        name        = request.form['name']
        description = request.form['description']
        if Category.query.filter_by(name=name).first():
            flash('Category already exists.', 'error')
        else:
            db.session.add(Category(name=name, description=description))
            db.session.commit()
            flash('Category added!', 'success')
            return redirect(url_for('list_categories'))
    return render_template('add_category.html')

@app.route('/categories/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_category(id):
    category = db.get_or_404(Category, id)
    if request.method == 'POST':
        category.name        = request.form['name']
        category.description = request.form['description']
        db.session.commit()
        flash('Category updated!', 'success')
        return redirect(url_for('list_categories'))
    return render_template('edit_category.html', category=category)

@app.route('/categories/delete/<int:id>', methods=['POST'])
@login_required
def delete_category(id):
    category = db.get_or_404(Category, id)
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted!', 'success')
    return redirect(url_for('list_categories'))

# ─────────────────────────────────────────
#  Budgets — CRUD
# ─────────────────────────────────────────
@app.route('/budgets')
@login_required
def list_budgets():
    now     = datetime.now()
    budgets = Budget.query.filter_by(user_id=current_user.id,
                                      month=now.month, year=now.year).all()
    budget_data = []
    for budget in budgets:
        spent = db.session.query(db.func.sum(Expense.amount)).filter(
            Expense.user_id     == current_user.id,
            Expense.category_id == budget.category_id,
            Expense.date.like(f'{now.year}-{str(now.month).zfill(2)}%')
        ).scalar() or 0
        pct = (spent / budget.amount * 100) if budget.amount > 0 else 0
        budget_data.append({
            'budget': budget, 'spent': spent,
            'remaining': budget.amount - spent,
            'percentage': min(pct, 100), 'over': spent > budget.amount
        })
    categories = Category.query.all()
    return render_template('budgets.html', budget_data=budget_data,
                           categories=categories, now=now)

@app.route('/budgets/add', methods=['GET', 'POST'])
@login_required
def add_budget():
    categories = Category.query.all()
    now        = datetime.now()
    if request.method == 'POST':
        category_id = request.form['category']
        amount      = float(request.form['amount'])
        month       = int(request.form['month'])
        year        = int(request.form['year'])
        existing    = Budget.query.filter_by(user_id=current_user.id,
                        category_id=category_id, month=month, year=year).first()
        if existing:
            flash('Budget for that category/month already exists.', 'error')
        else:
            db.session.add(Budget(user_id=current_user.id,
                category_id=category_id, amount=amount, month=month, year=year))
            db.session.commit()
            flash('Budget set!', 'success')
            return redirect(url_for('list_budgets'))
    return render_template('add_budget.html', categories=categories, now=now)

@app.route('/budgets/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_budget(id):
    budget = db.get_or_404(Budget, id)
    if budget.user_id != current_user.id:
        flash('Not authorized.', 'error')
        return redirect(url_for('list_budgets'))
    categories = Category.query.all()
    if request.method == 'POST':
        budget.amount = float(request.form['amount'])
        db.session.commit()
        flash('Budget updated!', 'success')
        return redirect(url_for('list_budgets'))
    return render_template('edit_budget.html', budget=budget, categories=categories)

@app.route('/budgets/delete/<int:id>', methods=['POST'])
@login_required
def delete_budget(id):
    budget = db.get_or_404(Budget, id)
    if budget.user_id != current_user.id:
        flash('Not authorized.', 'error')
        return redirect(url_for('list_budgets'))
    db.session.delete(budget)
    db.session.commit()
    flash('Budget removed.', 'success')
    return redirect(url_for('list_budgets'))

# ─────────────────────────────────────────
#  Run
# ─────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)