def calculate_pid(lin_id):
    """
    Вычисление Protected ID (PID) из ID путем добавления битов четности
    PID[0:5] = ID[0:5]
    PID[6] = P0 (четная четность для ID[0:4])
    PID[7] = P1 (нечетная четность для ID[0:5])
    """
    # Извлекаем биты ID
    id_bits = lin_id & 0x3F  # Получаем 6 бит ID
    
    # Вычисляем P0 (четная четность для ID[0:4])
    p0 = ((id_bits & 0x01) >> 0) ^ ((id_bits & 0x02) >> 1) ^ ((id_bits & 0x04) >> 2) ^ ((id_bits & 0x10) >> 4)
    
    # Вычисляем P1 (нечетная четность для ID[0:5])
    p1 = ~(((id_bits & 0x02) >> 1) ^ ((id_bits & 0x08) >> 3) ^ ((id_bits & 0x10) >> 4) ^ ((id_bits & 0x20) >> 5))
    
    # Объединяем ID и биты четности
    pid = ((p1 & 0x01) << 7) | ((p0 & 0x01) << 6) | id_bits
    return pid

def calculate_crc_enhanced(data, lin_id):
    """
    Вычисление CRC для сообщений LIN 2.0 (Расширенный метод)
    Расширенный CRC вычисляется как сумма всех байтов данных плюс protected ID
    
    Аргументы:
        data (list[int]): Список байтов данных
        id (int): ID сообщения (6 бит)
    
    Возвращает:
        int: Вычисленное значение CRC
    """
    # Вычисляем protected ID
    pid = calculate_pid(lin_id)
    
    # Начинаем с PID
    sum_with_carry = pid
    
    # Добавляем каждый байт данных
    for byte in data:
        sum_with_carry += byte
        # Обрабатываем перенос
        if sum_with_carry > 0xFF:
            sum_with_carry = (sum_with_carry & 0xFF) + 1
    
    # Инвертируем результат
    return (~sum_with_carry) & 0xFF 