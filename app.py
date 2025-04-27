from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, jsonify
from werkzeug.utils import secure_filename
import os
from lin_msg import LinMsg
import json
from crc import calculate_crc_enhanced
from auth import auth, db, login_manager
from flask_login import login_required

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
def index():
    return render_template('index.html')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                flash('No file part', 'error')
                return redirect(request.url)
            
            file = request.files['file']
            if file.filename == '':
                flash('No selected file', 'error')
                return redirect(request.url)
            
            if not allowed_file(file.filename):
                flash('Invalid file type. Please upload a CSV file.', 'error')
                return redirect(request.url)
            
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Проверяем, не существует ли уже файл с таким именем
            if os.path.exists(filepath):
                flash('File with this name already exists', 'error')
                return redirect(request.url)
            
            # Сохраняем файл
            file.save(filepath)
            
            # Проверяем, что файл не пустой
            if os.path.getsize(filepath) == 0:
                os.remove(filepath)
                flash('Uploaded file is empty', 'error')
                return redirect(request.url)
            
            # Обрабатываем CSV файл
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    csv_data = f.read()
                
                if not csv_data.strip():
                    os.remove(filepath)
                    flash('CSV file is empty', 'error')
                    return redirect(request.url)
                
                messages = LinMsg.process_csv_data(csv_data)
                
                if not messages:
                    os.remove(filepath)
                    flash('No valid LIN messages found in the file', 'error')
                    return redirect(request.url)
                
                # Сохраняем обработанные данные
                processed_filename = LinMsg.save_processed_data(messages, filename)
                
                if processed_filename:
                    # Удаляем исходный CSV файл, так как данные уже обработаны и сохранены
                    os.remove(filepath)
                    flash('File successfully uploaded and processed', 'success')
                    return redirect(url_for('data', filename=filename))
                else:
                    os.remove(filepath)
                    flash('Error processing file', 'error')
                    return redirect(request.url)
                    
            except Exception as e:
                if os.path.exists(filepath):
                    os.remove(filepath)
                flash(f'Error processing file: {str(e)}', 'error')
                return redirect(request.url)
                
        except Exception as e:
            flash(f'Error uploading file: {str(e)}', 'error')
            return redirect(request.url)
            
    return render_template('upload.html')

@app.route('/data')
@login_required
def data():
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
@login_required
def get_data():
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 