from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id           = db.Column(db.Integer, primary_key=True)
    username     = db.Column(db.String(100), unique=True, nullable=False)
    password     = db.Column(db.String(200), nullable=False)
    currency     = db.Column(db.String(10), default='$')    # Settings
    theme        = db.Column(db.String(10), default='light') # Dark mode pref

    def __repr__(self):
        return f'<User {self.username}>'


class Expense(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(100), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount      = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    date        = db.Column(db.String(20), nullable=False)
    receipt     = db.Column(db.String(300))    # Receipt upload (filename)
    upi_ref     = db.Column(db.String(100))    # UPI reference ID
    is_recurring = db.Column(db.Boolean, default=False)
    notes       = db.Column(db.String(300))

    def __repr__(self):
        return f'<Expense {self.amount} on {self.date}>'


class Category(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200))
    expenses    = db.relationship('Expense', backref='category',
                                  lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Category {self.name}>'


class Budget(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    amount      = db.Column(db.Float, nullable=False)
    month       = db.Column(db.Integer, nullable=False)
    year        = db.Column(db.Integer, nullable=False)
    category    = db.relationship('Category', backref='budgets')

    def __repr__(self):
        return f'<Budget {self.amount} cat={self.category_id}>'


# ─────────────────────────────────────────
#  NEW MODELS
# ─────────────────────────────────────────

class Income(db.Model):
    """A single income entry (salary, freelance, gift, etc.)."""
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(100), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount      = db.Column(db.Float, nullable=False)
    date        = db.Column(db.String(20), nullable=False)
    category    = db.Column(db.String(100))   # free-text: Salary, Freelance, Gift…
    notes       = db.Column(db.String(300))

    def __repr__(self):
        return f'<Income {self.amount} on {self.date}>'


class SavingsGoal(db.Model):
    """A named savings goal with target + current saved amount."""
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    saved_amount  = db.Column(db.Float, default=0)
    user_id       = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    deadline      = db.Column(db.String(20))   # YYYY-MM-DD, optional

    def __repr__(self):
        return f'<SavingsGoal {self.name} {self.saved_amount}/{self.target_amount}>'
