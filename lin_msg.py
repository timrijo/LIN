import csv
import os
import json
from flask import current_app

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
                
                # Проверка CRC
                if crc is not None and msg_pid is not None and all(x is not None for x in data):
                    from crc import calculate_crc_enhanced
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

    @classmethod
    def from_row_data(cls, time_value, values):
        """
        Создает объект LinMsg из данных строки CSV
        
        Args:
            time_value (float): временная метка
            values (list): список значений, где первый элемент - PID, 
                         последний - CRC, а между ними - данные
        
        Returns:
            LinMsg: новый объект сообщения
        """
        if not values:
            return cls()
        
        msg_pid = values[0] if values else None
        crc = values[-1] if len(values) > 1 else None
        data = values[1:-1] if len(values) > 2 else []
        
        return cls(msg_pid, data, crc, time_value)

    @staticmethod
    def get_unique_pids(messages):
        """
        Находит все уникальные PID в списке сообщений
        
        Args:
            messages (list[LinMsg]): список сообщений
        
        Returns:
            list[int]: отсортированный список уникальных PID (без None)
        """
        # Собираем все уникальные PID, исключая None
        unique_pids = {msg.pid for msg in messages if msg.pid is not None}
        # Возвращаем отсортированный список
        return sorted(unique_pids)

    @staticmethod
    def group_by_pid(messages):
        """
        Группирует сообщения по PID
        
        Args:
            messages (list[LinMsg]): список сообщений
        
        Returns:
            dict: словарь, где ключи - PID, значения - списки сообщений
        """
        groups = {}
        for msg in messages:
            if msg.pid is not None:
                if msg.pid not in groups:
                    groups[msg.pid] = []
                groups[msg.pid].append(msg)
        return groups

    @staticmethod
    def analyze_bit_changes(messages, target_pid):
        """
        Анализирует изменения битов в сообщениях с указанным PID
        
        Args:
            messages (list[LinMsg]): список сообщений
            target_pid (int): PID для анализа
        
        Returns:
            list: список изменений битов
        """
        changes = []
        prev_data = None
        
        for msg in messages:
            if msg.pid == target_pid and msg.data:
                if prev_data is not None:
                    for i, (prev, curr) in enumerate(zip(prev_data, msg.data)):
                        if prev != curr:
                            changes.append({
                                'time': msg.time,
                                'bit': i,
                                'from': prev,
                                'to': curr
                            })
                prev_data = msg.data
        
        return changes

    @staticmethod
    def format_bit_changes(changes):
        """
        Форматирует изменения битов для отображения
        
        Args:
            changes (list): список изменений битов
        
        Returns:
            str: отформатированная строка
        """
        if not changes:
            return "Нет изменений"
        
        result = []
        for change in changes:
            result.append(
                f"Время: {change['time']:.3f}, "
                f"Бит {change['bit']}: "
                f"{change['from']} -> {change['to']}"
            )
        
        return "\n".join(result)

    @staticmethod
    def analyze_single_bit_changes(messages, target_pid):
        """
        Анализирует изменения отдельных битов в сообщениях с указанным PID
        
        Args:
            messages (list[LinMsg]): список сообщений
            target_pid (int): PID для анализа
        
        Returns:
            dict: словарь с изменениями для каждого бита
        """
        bit_changes = {}
        prev_data = None
        
        for msg in messages:
            if msg.pid == target_pid and msg.data:
                if prev_data is not None:
                    for i, (prev, curr) in enumerate(zip(prev_data, msg.data)):
                        if prev != curr:
                            if i not in bit_changes:
                                bit_changes[i] = []
                            bit_changes[i].append({
                                'time': msg.time,
                                'from': prev,
                                'to': curr
                            })
                prev_data = msg.data
        
        return bit_changes 