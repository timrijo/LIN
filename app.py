from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pandas as pd
import numpy as np
import os
from lin_msg import LinMsg
import json
import csv
from crc import calculate_crc_enhanced

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

def save_processed_data(messages, filename):
    """
    Сохраняет обработанные данные в отдельный файл.
    Args:
        messages: список объектов LinMsg
        filename: имя исходного файла
    """
    try:
        # Создаем имя для файла с обработанными данными
        processed_filename = f"processed_{filename}"
        processed_filepath = os.path.join(app.config['UPLOAD_FOLDER'], processed_filename)
        
        # Сохраняем данные в JSON файл, каждое сообщение в отдельной строке
        with open(processed_filepath, 'w', encoding='utf-8') as f:
            for msg in messages:
                data_to_save = {
                    'pid': msg.pid,
                    'data': msg.data,
                    'crc': msg.crc,
                    'time': msg.time
                }
                json.dump(data_to_save, f, ensure_ascii=False)
                f.write('\n')  # Добавляем перенос строки после каждого сообщения
            
        return processed_filename
    except Exception as e:
        return None

def process_csv_data(csv_data):
    """Обрабатывает данные CSV и возвращает список объектов LinMsg"""
    messages = []
    reader = csv.reader(csv_data.splitlines())
    
    # Пропускаем заголовок
    next(reader)
    
    for row in reader:
        if not row:  # Пропускаем пустые строки
            continue
            
        try:
            # Проверяем минимальное количество столбцов
            if len(row) < 7:  # Минимум 7 столбцов: время, Break, время, SYNC, время, PID, время
                continue
                
            # Столбец 0: время начала сообщения
            time_value = float(row[0])
            
            # Столбец 1: Break (должен быть 0x00)
            if row[1] != '0x00':
                continue
            
            # Столбец 3: SYNC (должен быть 0x55)
            if row[3] != '0x55':
                continue
            
            # Столбец 5: PID
            msg_pid = None
            if row[5].startswith('0x'):
                msg_pid = int(row[5], 16)
            else:
                msg_pid = int(row[5])
            
            # Обрабатываем данные (столбцы 7 и далее через один)
            data = []
            crc = None
            
            # Начинаем с 7-го столбца и берем каждый второй столбец до предпоследнего
            for i in range(7, len(row) - 1, 2):
                try:
                    value = row[i]
                    if value.startswith('0x'):
                        value_int = int(value, 16)
                    else:
                        value_int = int(value)
                    data.append(value_int)
                except (IndexError, ValueError):
                    data.append(None)
            
            # CRC берется из последнего столбца
            try:
                crc_value = row[-1]  # Последний столбец
                if crc_value.startswith('0x'):
                    crc = int(crc_value, 16)
                else:
                    crc = int(crc_value)
            except (IndexError, ValueError):
                crc = None
            
            # Проверка CRC акомментирована
            if crc is not None and msg_pid is not None and all(x is not None for x in data):
                 from crc import calculate_crc_enhanced
                 crc_enhanced = calculate_crc_enhanced(data, msg_pid)
                 
                 # Если CRC не совпадает ни с одним из методов, пропускаем сообщение
                 if crc != crc_enhanced:
                     continue
            
            # Создаем объект сообщения
            msg = LinMsg(msg_pid, data, crc, time_value)
            messages.append(msg)
            
        except Exception:
            continue
    
    return messages

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """
    Маршрут для загрузки CSV файла.
    """
    filename = None
    error = None

    if request.method == 'POST':
        try:
            # Проверяем, есть ли файл в запросе
            if 'file' not in request.files:
                error = 'Файл не был загружен'
                return render_template('upload.html', error=error)
            
            file = request.files['file']
            
            # Проверяем, был ли выбран файл
            if file.filename == '':
                error = 'Файл не выбран'
                return render_template('upload.html', error=error)
            
            # Проверяем расширение файла
            if not allowed_file(file.filename):
                error = 'Разрешены только CSV файлы'
                return render_template('upload.html', error=error)
            
            # Сохраняем файл
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Обрабатываем данные и сохраняем в отдельный файл
            with open(filepath, 'r', encoding='utf-8') as f:
                messages = process_csv_data(f.read())
            
            processed_filename = save_processed_data(messages, filename)
            
            if not processed_filename:
                error = 'Ошибка при сохранении обработанных данных'
                return render_template('upload.html', error=error)
            
            return redirect(url_for('data', filename=filename))
            
        except Exception as e:
            error = f'Ошибка загрузки файла: {str(e)}'
            return render_template('upload.html', error=error)

    return render_template('upload.html', filename=filename, error=error)

@app.route('/data')
def data():
    """
    Маршрут для просмотра данных из загруженного CSV файла.
    Ожидает параметр filename с именем файла.
    """
    filename = request.args.get('filename')
    messages = None
    error = None
    unique_pids = None

    if not filename:
        return redirect(url_for('upload'))
    
    try:
        # Формируем имя файла с обработанными данными
        processed_filename = f"processed_{filename}"
        processed_filepath = os.path.join(app.config['UPLOAD_FOLDER'], processed_filename)
        
        # Проверяем существование файла
        if not os.path.exists(processed_filepath):
            error = f'Файл с обработанными данными не найден'
            return render_template('data.html', error=error)
        
        # Читаем данные из файла построчно
        messages = []
        with open(processed_filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():  # Пропускаем пустые строки
                    msg_data = json.loads(line)
                    # Создаем объект LinMsg из данных
                    lin_msg = LinMsg(
                        msg_pid=msg_data['pid'],
                        data=msg_data['data'],
                        crc=msg_data['crc'],
                        time=msg_data['time']
                    )
                    messages.append(lin_msg)
        
        # Получаем уникальные PID
        if messages:
            unique_pids = sorted(set(msg.pid for msg in messages if msg.pid is not None))
        
    except Exception as e:
        error = f'Ошибка загрузки данных: {str(e)}'
        return render_template('data.html', error=error)

    return render_template('data.html', 
                         messages=messages, 
                         filename=filename, 
                         error=error, 
                         unique_pids=unique_pids)

@app.route('/get_data')
def get_data():
    """
    Маршрут для получения данных через AJAX.
    Ожидает параметр filename с именем файла.
    Возвращает JSON с данными или ошибкой.
    """
    filename = request.args.get('filename')
    
    if not filename:
        return jsonify({'error': 'Имя файла не указано'}), 400
    
    try:
        # Формируем имя файла с обработанными данными
        processed_filename = f"processed_{filename}"
        processed_filepath = os.path.join(app.config['UPLOAD_FOLDER'], processed_filename)
        
        # Проверяем существование файла
        if not os.path.exists(processed_filepath):
            return jsonify({'error': f'Файл с обработанными данными не найден'}), 404
        
        # Читаем данные из файла построчно
        messages_data = []
        with open(processed_filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():  # Пропускаем пустые строки
                    messages_data.append(json.loads(line))
        
        return jsonify({'messages': messages_data})
    
    except Exception as e:
        return jsonify({'error': f'Ошибка загрузки данных: {str(e)}'}), 500

class LinMsg:
    def __init__(self, msg_pid, data, crc, time):
        self.pid = msg_pid
        self.data = data
        self.crc = crc
        self.time = time
    
    def to_dict(self):
        return {
            'pid': self.pid,
            'data': self.data,
            'crc': self.crc,
            'time': self.time
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            msg_pid=data.get('pid'),
            data=data.get('data', []),
            crc=data.get('crc'),
            time=data.get('time')
        )

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 