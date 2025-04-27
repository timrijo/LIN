from crc import calculate_crc_classic, calculate_crc_enhanced, calculate_pid

# Тестовые сообщения из файла
test_messages = [
    {"pid": 1, "data": [0, 0, 0, 252, 255, 255, 255, 255], "crc": 65, "time": 0.006697708333333},
    {"pid": 36, "data": [228, 212, 100, 165], "crc": 215, "time": 0.016711083333333},
    {"pid": 40, "data": [10, 10, 0, 17, 32, 2, 0, 0], "crc": 16, "time": 0.026733},
    {"pid": 41, "data": [0, 0, 252, 0, 0, 0, 0, 254], "crc": 26, "time": 0.03670375},
    {"pid": 42, "data": [0, 0, 0, 0, 248, 255, 255, 255], "crc": 156, "time": 0.046706833333333},
    {"pid": 43, "data": [0, 128, 0, 128, 128, 8, 2, 128], "crc": 200, "time": 0.056696875},
    {"pid": 1, "data": [0, 0, 0, 252, 255, 255, 255, 255], "crc": 65, "time": 0.076696583333333}
]

print("Проверка CRC для сообщений:")
print("-" * 70)
print("PID | ID | Данные | Ожидаемый CRC | Классический CRC | Расширенный CRC")
print("-" * 70)

for msg in test_messages:
    # Извлекаем ID из PID (первые 6 бит)
    id = msg["pid"] & 0x3F
    # Проверяем, что PID совпадает с рассчитанным
    calculated_pid = calculate_pid(id)
    
    classic_crc = calculate_crc_classic(msg["data"], id)
    enhanced_crc = calculate_crc_enhanced(msg["data"], id)
    
    print(f"{msg['pid']:3d} | {id:3d} | {msg['data']} | {msg['crc']:3d} | {classic_crc:3d} | {enhanced_crc:3d}") 