from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id           = db.Column(db.Integer, primary_key=True)
    username     = db.Column(db.String(100), unique=True, nullable=False)
    password     = db.Column(db.String(200), nullable=False)
    currency     = db.Column(db.String(10), default='$')    # ← NEW: Settings
    theme        = db.Column(db.String(10), default='light') # ← NEW: Dark mode pref

    def __repr__(self):
        return f'<User {self.username}>'


class Expense(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(100), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount      = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    date        = db.Column(db.String(20), nullable=False)
    receipt     = db.Column(db.String(300))   # ← NEW: Receipt upload (file path)
    upi_ref     = db.Column(db.String(100))   # ← NEW: UPI reference ID
    is_recurring = db.Column(db.Boolean, default=False)  # ← NEW: Recurring flag
    notes       = db.Column(db.String(300))   # ← NEW: Optional notes

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