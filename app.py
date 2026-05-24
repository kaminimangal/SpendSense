from flask import Flask,render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from models import db, User, Expense, Category

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return render_template('dashboard.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose a different one.', 'error')
            # return redirect(url_for('register'))
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
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'error')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    # categories = Category.query.filter_by(user_id=current_user.id).all(
    category_totals = {}
    for expense in expenses:
        category_name = expense.category.name if expense.category else 'Uncategorized'
        category_totals[category_name] = category_totals.get(category_name, 0) + expense.amount
    
    suggestions = []
    if category_totals:
        max_category = max(category_totals, key=category_totals.get)
        max_amount = category_totals[max_category]
        if max_amount > 3000:  # Arbitrary threshold for high spending
            suggestions.append(f'You have spent ${max_amount} on {max_category}. Consider reviewing your expenses in this category.')
        else:
            suggestions.append('Your spending is within a reasonable range. Keep it up!')
    return render_template('dashboard.html',
                           username=current_user.username,
                           expenses=expenses,
                           categories = list(category_totals.keys()),
                           totals = list(category_totals.values()),
                           suggestions=suggestions)

@app.route('/add', methods=['GET','POST'])
@login_required 
def add_expense():
    categories = Category.query.all()
    if request.method == 'POST':
        title = request.form['title']
        amount = float(request.form['amount'])
        date = request.form['date']
        category_id = request.form['category']

        new_expense = Expense(title=title, 
                            amount=amount, 
                            date = date,
                            user_id=current_user.id,
                            category_id=category_id)
        db.session.add(new_expense)
        db.session.commit()
        flash('Expense added successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_expense.html', categories=categories)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_expense(id):
    expense = Expense.query.get_or_404(id)
    if expense.user_id != current_user.id:
        flash('You are not authorized to edit this expense.', 'error')
        return redirect(url_for('dashboard'))
    categories = Category.query.all()
    if request.method == 'POST':
        expense.title = request.form['title']
        expense.amount = float(request.form['amount'])
        expense.date = request.form['date']
        expense.category_id = request.form['category']
        db.session.commit()
        flash('Expense updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('edit_expense.html', expense=expense, categories=categories)

@app.route('/delete/<int:id>',methods=['POST'])
@login_required
def delete_expense(id):
    expense = Expense.query.get_or_404(id)
    if expense.user_id != current_user.id:
        flash('You are not authorized to delete this expense.', 'error')
        return redirect(url_for('dashboard'))
    db.session.delete(expense)
    db.session.commit()
    flash('Expense deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required 
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

#categories CRUD operations
@app.route('/categories')
@login_required
def list_categories():
    categories = Category.query.all()
    return render_template('categories.html', categories=categories)
        
@app.route('/categories/add', methods=['GET','POST'])
@login_required 
def add_category():
    # categories = Category.query.all()
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        if Category.query.filter_by(name=name).first():
            flash('Category already exists. Please choose a different name.', 'error')
        else:
            new_category = Category(name=name, description=description)
            db.session.add(new_category)
            db.session.commit()
            flash('Category added successfully!', 'success')
            return redirect(url_for('list_categories'))
    return render_template('add_category.html')

@app.route('/categories/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_category(id):
    category = Category.query.get_or_404(id)
    if request.method == 'POST':
        category.name = request.form['name']
        category.description = request.form['description']
        db.session.commit()
        flash('Category updated successfully!', 'success')
        return redirect(url_for('list_categories'))
    return render_template('edit_category.html', category=category)
    
@app.route('/categories/delete/<int:id>')
@login_required
def delete_category(id):
    category = Category.query.get_or_404(id)
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted successfully!', 'success')
    return redirect(url_for('list_categories'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)


