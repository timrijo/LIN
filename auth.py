from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

# Инициализация базы данных
db = SQLAlchemy()

# Модель пользователя
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    name = db.Column(db.String(100))
    password = db.Column(db.String(200))

    def __init__(self, email, name, password):
        self.email = email
        self.name = name
        self.password = password

    def check_password(self, password):
        return check_password_hash(self.password, password)

# Инициализация менеджера авторизации
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Blueprint для маршрутов авторизации
auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, password):
            flash('Пожалуйста, проверьте свои данные и попробуйте снова.')
            return redirect(url_for('auth.login'))

        login_user(user, remember=remember)
        return redirect(url_for('index'))

    return render_template('login.html')

@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user:
            flash('Email уже зарегистрирован')
            return redirect(url_for('auth.signup'))

        new_user = User(email=email, name=name, password=generate_password_hash(password, method='sha256'))

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('auth.login'))

    return render_template('signup.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@auth.route('/profile')
@login_required
def profile():
    return render_template('profile.html', name=current_user.name)

@auth.route('/profile/change_password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Проверяем текущий пароль
    if not current_user.check_password(current_password):
        flash('Неверный текущий пароль', 'error')
        return redirect(url_for('auth.profile'))
    
    # Проверяем совпадение новых паролей
    if new_password != confirm_password:
        flash('Новые пароли не совпадают', 'error')
        return redirect(url_for('auth.profile'))
    
    # Обновляем пароль
    current_user.password = generate_password_hash(new_password)
    try:
        db.session.commit()
        flash('Пароль успешно изменен', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при изменении пароля', 'error')
        print(f"Ошибка при изменении пароля: {str(e)}")
    
    return redirect(url_for('auth.profile')) 