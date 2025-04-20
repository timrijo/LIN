from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pandas as pd
import numpy as np
import os
from lin_msg import LinMsg

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'csv'}

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', name=current_user.name)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, password):
            flash('Please check your login details and try again.')
            return redirect(url_for('login'))

        login_user(user, remember=remember)
        return redirect(url_for('profile'))

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user:
            flash('Email address already exists')
            return redirect(url_for('signup'))

        new_user = User(email=email,
                       name=name,
                       password=generate_password_hash(password, method='sha256'))

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_csv_data(filepath):
    try:
        # Читаем файл, пропуская первую строку
        df = pd.read_csv(filepath, header=None, skiprows=1)
        
        # Список для хранения сообщений
        messages = []
        
        # Проходим по каждой строке
        for index, row in df.iterrows():
            time_value = float(row[0])
            
            # Собираем данные из строки
            values = []
            for col_idx in range(5, len(row), 2):  # Формула 2n+5
                if col_idx < len(row):
                    try:
                        value = str(row[col_idx]).replace('0x', '').strip()
                        if value:
                            values.append(int(value, 16))
                        else:
                            values.append(None)
                    except ValueError:
                        values.append(None)
                else:
                    values.append(None)
            
            # Создаем объект LinMsg
            if values:  # Если есть хотя бы одно значение
                lin_msg = LinMsg.from_row_data(time_value, values)
                messages.append(lin_msg)
        
        return messages
    except Exception as e:
        raise Exception(f'Ошибка обработки файла: {str(e)}')

@app.route('/data', methods=['GET', 'POST'])
def data():
    messages = None
    filename = None
    error = None
    unique_ids = None

    if request.method == 'POST':
        # Проверяем, есть ли файл в запросе
        if 'file' not in request.files:
            error = 'Файл не был загружен'
            return render_template('data.html', error=error)
        
        file = request.files['file']
        
        # Проверяем, был ли выбран файл
        if file.filename == '':
            error = 'Файл не выбран'
            return render_template('data.html', error=error)
        
        # Проверяем расширение файла
        if not allowed_file(file.filename):
            error = 'Разрешены только CSV файлы'
            return render_template('data.html', error=error)
        
        try:
            # Сохраняем файл
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Обрабатываем данные
            messages = process_csv_data(filepath)
            
            # Получаем уникальные ID
            if messages:
                unique_ids = LinMsg.get_unique_ids(messages)
            
        except Exception as e:
            error = f'Ошибка обработки файла: {str(e)}'
            return render_template('data.html', error=error)

    return render_template('data.html', 
                         messages=messages, 
                         filename=filename, 
                         error=error, 
                         unique_ids=unique_ids)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 