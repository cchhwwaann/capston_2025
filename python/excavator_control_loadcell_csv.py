import serial
import keyboard
import time
import matplotlib.pyplot as plt
from collections import deque
import csv # CSV 저장을 위한 라이브러리

# 🚨 아두이노 포트 확인
PORT = 'COM5'
BAUD_RATE = 115200 

try:
    ser = serial.Serial(PORT, BAUD_RATE, timeout=0.05)
    print(f"포트 {PORT} 연결 성공 (속도: {BAUD_RATE})")
    time.sleep(2) 
except Exception as e:
    print(f"포트 연결 실패: {e}")
    exit()

# --- CSV 파일 생성 ---
filename = "sensor_data.csv"
csv_file = open(filename, 'w', newline='')
writer = csv.writer(csv_file)
# 헤더(제목) 작성
writer.writerow(['Time', 'Sensor1', 'Sensor2'])
print(f"=== 데이터 저장 시작: {filename} ===")
print("=== 'ESC' 종료 ===")

# --- 제어 설정 ---
key_map = {
    'i': ('i', 'I'), 'k': ('k', 'K'),
    'w': ('w', 'W'), 's': ('s', 'S'),
    'j': ('j', 'J'), 'l': ('l', 'L')
}
key_pressed_state = {key: False for key in key_map.keys()}
running = True

def send_cmd(cmd):
    try:
        ser.write(cmd.encode())
    except: pass

def on_key_event(event):
    global running
    if event.name == 'esc':
        running = False
        return
    if event.name in key_map:
        press, release = key_map[event.name]
        if event.event_type == 'down' and not key_pressed_state[event.name]:
            send_cmd(press)
            key_pressed_state[event.name] = True
        elif event.event_type == 'up':
            send_cmd(release)
            key_pressed_state[event.name] = False

keyboard.hook(on_key_event)

# --- 플롯 설정 ---
MAX_POINTS = 100
data1 = deque([0]*MAX_POINTS, maxlen=MAX_POINTS)
data2 = deque([0]*MAX_POINTS, maxlen=MAX_POINTS)

plt.ion()
fig, ax = plt.subplots()
ax.set_title("Real-time Raw Data Monitoring")
ax.set_xlabel("Recent Samples")
ax.set_ylabel("Raw Value")
ax.grid(True)

line1, = ax.plot([], [], 'r-', label='Sensor 1', linewidth=1.5)
line2, = ax.plot([], [], 'b-', label='Sensor 2', linewidth=1.5)
ax.legend(loc='upper left')

# 시작 시간 기록 (상대 시간 계산용)
start_time = time.time()

print("\n--- 데이터 수집 및 기록 중... ---")

try:
    while running:
        while ser.in_waiting > 0:
            try:
                line_str = ser.readline().decode('utf-8').strip()
                
                if ',' in line_str:
                    parts = line_str.split(',')
                    if len(parts) >= 2:
                        val1 = int(parts[0])
                        val2 = int(parts[1])
                        
                        # 1. 현재 시간 (0초부터 시작하도록 계산)
                        current_time = time.time() - start_time
                        
                        # 2. CSV 파일에 저장 [시간, 값1, 값2]
                        writer.writerow([round(current_time, 4), val1, val2])

                        # 3. 그래프용 데이터 업데이트
                        data1.append(val1)
                        data2.append(val2)

            except: pass
        
        # 그래프 업데이트 (화면 표시용)
        line1.set_ydata(data1)
        line1.set_xdata(range(len(data1)))
        
        line2.set_ydata(data2)
        line2.set_xdata(range(len(data2)))
        
        ax.relim()
        ax.autoscale_view(scalex=False, scaley=True)
        
        plt.pause(0.02)

finally:
    # 종료 시 파일 닫기 (중요)
    csv_file.close() 
    plt.close()
    if ser.is_open:
        for key, cmds in key_map.items():
            send_cmd(cmds[1]) 
        ser.close()
    print(f"\n종료되었습니다. 데이터가 '{filename}'에 저장되었습니다.")