from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from werkzeug.utils import secure_filename
import os
from lin_msg import LinMsg
import json
from auth import auth, db, login_manager
from flask_login import login_required
from crc import calculate_pid, calculate_crc_enhanced

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {'csv'}

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db.init_app(app)
login_manager.init_app(app)
app.register_blueprint(auth)

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/calculator')
@login_required
def calculator():
    return render_template('calculator.html')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                flash('Файл не был выбран', 'error')
                return redirect(request.url)
            
            file = request.files['file']
            if file.filename == '':
                flash('Файл не выбран', 'error')
                return redirect(request.url)
            
            if not allowed_file(file.filename):
                flash('Недопустимый тип файла. Пожалуйста, загрузите CSV-файл.', 'error')
                return redirect(request.url)
            
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Проверяем, не существует ли уже файл с таким именем
            if os.path.exists(filepath):
                flash('Файл с таким именем уже существует', 'error')
                return redirect(request.url)
            
            # Сохраняем файл
            file.save(filepath)
            
            # Проверяем, что файл не пустой
            if os.path.getsize(filepath) == 0:
                os.remove(filepath)
                flash('Загруженный файл пустой', 'error')
                return redirect(request.url)
            
            # Обрабатываем CSV файл
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    csv_data = f.read()
                
                if not csv_data.strip():
                    os.remove(filepath)
                    flash('CSV-файл пустой', 'error')
                    return redirect(request.url)
                
                messages = LinMsg.process_csv_data(csv_data)
                
                if not messages:
                    os.remove(filepath)
                    flash('В файле не найдено допустимых LIN-сообщений', 'error')
                    return redirect(request.url)
                
                # Сохраняем обработанные данные
                processed_filename = LinMsg.save_processed_data(messages, filename)
                
                if processed_filename:
                    # Удаляем исходный CSV файл, так как данные уже обработаны и сохранены
                    os.remove(filepath)
                    flash('Файл успешно загружен и обработан', 'success')
                    return redirect(url_for('data', filename=filename))
                else:
                    os.remove(filepath)
                    flash('Ошибка при обработке файла', 'error')
                    return redirect(request.url)
                    
            except Exception as e:
                if os.path.exists(filepath):
                    os.remove(filepath)
                flash(f'Ошибка при обработке файла: {str(e)}', 'error')
                return redirect(request.url)
                
        except Exception as e:
            flash(f'Ошибка при загрузке файла: {str(e)}', 'error')
            return redirect(request.url)
            
    return render_template('upload.html')

@app.route('/data')
@login_required
def data():
    filename = request.args.get('filename')
    is_json = request.args.get('format') == 'json'
    
    if not filename:
        if is_json:
            return jsonify({'error': 'Имя файла не указано'}), 400
        return redirect(url_for('upload'))
    
    try:
        # Формируем имя файла с обработанными данными
        processed_filename = f"processed_{filename}"
        processed_filepath = os.path.join(app.config['UPLOAD_FOLDER'], processed_filename)
        
        # Проверяем существование файла
        if not os.path.exists(processed_filepath):
            error = f'Файл с обработанными данными не найден'
            if is_json:
                return jsonify({'error': error}), 404
            return render_template('data.html', error=error)
        
        # Читаем данные из файла построчно
        messages = []
        messages_data = []
        with open(processed_filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():  # Пропускаем пустые строки
                    msg_data = json.loads(line)
                    messages_data.append(msg_data)
                    # Создаем объект LinMsg из данных
                    lin_msg = LinMsg(
                        msg_pid=msg_data['pid'],
                        data=msg_data['data'],
                        crc=msg_data['crc'],
                        time=msg_data['time']
                    )
                    messages.append(lin_msg)
        
        # Получаем уникальные PID
        unique_pids = sorted(set(msg.pid for msg in messages if msg.pid is not None)) if messages else None
        
        if is_json:
            return jsonify({'messages': messages_data})
        
        return render_template('data.html', 
                             messages=messages, 
                             filename=filename, 
                             error=None, 
                             unique_pids=unique_pids)
        
    except Exception as e:
        error = f'Ошибка загрузки данных: {str(e)}'
        if is_json:
            return jsonify({'error': error}), 500
        return render_template('data.html', error=error)

@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        lin_data = request.get_json()
        
        # Проверяем входные данные
        if not lin_data or 'id' not in lin_data or 'data' not in lin_data:
            return jsonify({'error': 'Неверные входные данные'}), 400
            
        protected_id = lin_data['id']
        data_bytes = lin_data['data']
        
        # Проверяем ID
        if not isinstance(protected_id, int) or protected_id < 0 or protected_id > 0x3F:
            return jsonify({'error': 'ID должен быть между 0 и 0x3F'}), 400
            
        # Проверяем байты данных
        if not isinstance(data_bytes, list):
            return jsonify({'error': 'Данные должны быть массивом'}), 400
            
        for byte in data_bytes:
            if not isinstance(byte, int) or byte < 0 or byte > 0xFF:
                return jsonify({'error': 'Байты данных должны быть между 0 и 0xFF'}), 400
        
        # Вычисляем PID и CRC используя функции из crc.py
        pid = calculate_pid(protected_id)
        crc = calculate_crc_enhanced(data_bytes, protected_id)
        
        if pid is None or crc is None:
            return jsonify({'error': 'Ошибка при вычислении PID или CRC'}), 500
        
        # Подготавливаем ответ
        response = {
            'pid': pid,
            'crc': crc,
            'message': [pid] + data_bytes + [crc]
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 