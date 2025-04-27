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
            dict[int, list[LinMsg]]: словарь, где ключ - PID, значение - список сообщений с этим PID
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
            messages (list[LinMsg]): список всех сообщений
            target_pid (int): PID для анализа
        
        Returns:
            list[dict]: список изменений битов между последовательными сообщениями
        """
        # Фильтруем сообщения по PID и сортируем по времени
        pid_messages = sorted(
            [msg for msg in messages if msg.pid == target_pid],
            key=lambda x: x.time
        )
        
        if len(pid_messages) < 2:
            return []

        changes = []
        
        # Анализируем каждую пару последовательных сообщений
        for i in range(len(pid_messages) - 1):
            current_msg = pid_messages[i]
            next_msg = pid_messages[i + 1]
            
            # Проверяем каждый байт данных
            byte_changes = []
            for byte_idx, (current_byte, next_byte) in enumerate(zip(current_msg.data, next_msg.data)):
                if current_byte is None or next_byte is None:
                    continue
                    
                # Находим изменившиеся биты
                changed_bits = current_byte ^ next_byte
                if changed_bits != 0:
                    # Проверяем, является ли изменение однобитовым
                    is_single_bit = bin(changed_bits).count('1') == 1
                    if is_single_bit:
                        # Определяем номер изменившегося бита
                        bit_position = bin(changed_bits)[::-1].index('1')
                        byte_changes.append({
                            'byte_index': byte_idx,
                            'bit_position': bit_position,
                            'old_value': bool(current_byte & (1 << bit_position)),
                            'new_value': bool(next_byte & (1 << bit_position)),
                            'time_diff': next_msg.time - current_msg.time
                        })
            
            if byte_changes:
                changes.append({
                    'time_start': current_msg.time,
                    'time_end': next_msg.time,
                    'changes': byte_changes
                })

        return changes

    @staticmethod
    def format_bit_changes(changes):
        """
        Форматирует результаты анализа изменений битов в читаемый вид
        
        Args:
            changes (list[dict]): результат работы analyze_bit_changes
        
        Returns:
            list[str]: список строк с описанием изменений
        """
        result = []
        for change in changes:
            for byte_change in change['changes']:
                result.append(
                    f"Time: {change['time_start']:.3f} -> {change['time_end']:.3f} "
                    f"(Δt: {byte_change['time_diff']:.3f}s), "
                    f"Byte {byte_change['byte_index'] + 1}, "
                    f"Bit {byte_change['bit_position']}: "
                    f"{int(byte_change['old_value'])} -> {int(byte_change['new_value'])}"
                )
        return result

    @staticmethod
    def analyze_single_bit_changes(messages, target_pid):
        """
        Анализирует изменения одиночных битов в сообщениях с указанным PID
        
        Args:
            messages (list[LinMsg]): список всех сообщений
            target_pid (int): PID для анализа
        
        Returns:
            list: список словарей с информацией об изменениях одиночных битов
                 [
                     {
                         'time': время изменения,
                         'byte_index': индекс байта,
                         'bit_index': индекс бита,
                         'old_value': предыдущее значение,
                         'new_value': новое значение
                     },
                     ...
                 ]
        """
        # Фильтруем сообщения по PID и сортируем по времени
        pid_messages = sorted(
            [msg for msg in messages if msg.pid == target_pid],
            key=lambda x: x.time
        )
        
        changes = []
        
        # Нужно минимум два сообщения для сравнения
        if len(pid_messages) < 2:
            return changes

        # Сравниваем каждую пару последовательных сообщений
        for i in range(len(pid_messages) - 1):
            current_msg = pid_messages[i]
            next_msg = pid_messages[i + 1]
            
            # Проверяем каждый байт в сообщении
            for byte_idx, (current_byte, next_byte) in enumerate(zip(current_msg.data, next_msg.data)):
                if current_byte is None or next_byte is None:
                    continue
                
                # Находим изменившиеся биты (XOR покажет все изменённые биты как 1)
                diff = current_byte ^ next_byte
                
                # Проверяем, изменился ли только один бит (число должно быть степенью двойки)
                if diff != 0 and (diff & (diff - 1)) == 0:
                    # Находим индекс изменившегося бита
                    bit_index = 0
                    while diff > 1:
                        diff >>= 1
                        bit_index += 1
                    
                    changes.append({
                        'time': next_msg.time,
                        'byte_index': byte_idx,
                        'bit_index': bit_index,
                        'old_value': bool(current_byte & (1 << bit_index)),
                        'new_value': bool(next_byte & (1 << bit_index))
                    })

        return changes 