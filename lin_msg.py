import csv
import os
import json
from flask import current_app
from crc import calculate_crc_enhanced, calculate_pid

class LinMsg:
    def __init__(self, msg_pid=None, data=None, crc=None, time=None):
        self.pid = msg_pid      # PID сообщения
        self.data = data if data is not None else []  # Список данных
        self.crc = crc        # Значение CRC
        self.time = time      # Временная метка

    def __str__(self):
        data_str = ', '.join([f'0x{x:02X}' if x is not None else 'None' for x in self.data])
        pid_str = f'0x{self.pid:02X}' if self.pid is not None else 'None'
        crc_str = f'0x{self.crc:02X}' if self.crc is not None else 'None'
        time_str = f'{self.time:.3f}' if self.time is not None else 'None'
        return f"PID: {pid_str}, Data: [{data_str}], CRC: {crc_str}, Time: {time_str}"

    @classmethod
    def process_csv_data(cls, csv_data):
        """
        Обрабатывает данные CSV и возвращает список объектов LinMsg
        
        Args:
            csv_data (str): содержимое CSV файла в виде строки
            
        Returns:
            list: список объектов LinMsg
        """
        messages = []
        reader = csv.reader(csv_data.splitlines())
        
        # Пропускаем заголовок
        next(reader)
        
        for row in reader:
            if not row:  # Пропускаем пустые строки
                continue
                
            try:
                # Проверяем минимальное количество столбцов
                if len(row) < 6:  # Минимум 7 столбцов: время, Break, время, SYNC, время, PID
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
                
                # Проверка CRC
                if crc is not None and msg_pid is not None:
                    # Проверяем, есть ли данные D
                    if all(x is not None for x in data):
                        crc_enhanced = calculate_crc_enhanced(data, msg_pid)
                        
                        # Если CRC не совпадает ни с одним из методов, пропускаем сообщение
                        if crc != crc_enhanced:
                            continue
                
                # Создаем объект сообщения
                msg = cls(msg_pid, data, crc, time_value)
                messages.append(msg)
                
            except Exception:
                continue
        
        return messages

    @staticmethod
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
            processed_filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], processed_filename)
            
            print(f"Сохранение обработанных данных в файл: {processed_filepath}")
            print(f"Количество сообщений для сохранения: {len(messages)}")
            
            # Сохраняем данные в JSON файл, каждое сообщение в отдельной строке
            with open(processed_filepath, 'w', encoding='utf-8') as f:
                for msg in messages:
                    json.dump({
                        'pid': msg.pid,
                        'data': msg.data,
                        'crc': msg.crc,
                        'time': msg.time
                    }, f, ensure_ascii=False)
                    f.write('\n')
                    
            return processed_filepath
        except Exception as e:
            print(f"Ошибка при сохранении обработанных данных: {e}")
            return None