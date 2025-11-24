import serial
import keyboard
import time
import matplotlib.pyplot as plt
from collections import deque

# 🚨 아두이노 포트 확인
PORT = 'COM5'
# 🚀 아두이노 설정에 맞춰 115200 유지
BAUD_RATE = 115200 

try:
    ser = serial.Serial(PORT, BAUD_RATE, timeout=0.05)
    print(f"포트 {PORT} 연결 성공 (속도: {BAUD_RATE})")
    time.sleep(2) 
except Exception as e:
    print(f"포트 연결 실패: {e}")
    exit()

print("=== 굴삭기 Dual Sensor 변화 강도 (절댓값 |0 ~ 1|) 플로팅 ===")
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

# --- 플롯 데이터 설정 ---
MAX_POINTS = 100
intensity_data1 = deque([0]*MAX_POINTS, maxlen=MAX_POINTS)
intensity_data2 = deque([0]*MAX_POINTS, maxlen=MAX_POINTS)

prev_val1 = None
prev_val2 = None

# ==========================================
# ⚙️ [개별 감도 조절] 
# 값이 클수록 둔감해지고, 작을수록 민감해집니다.
# 절댓값을 쓰면 진동도 '신호'로 잡히므로 감도를 조금 높이는(둔감하게) 게 좋을 수 있습니다.
# ==========================================
SENSITIVITY1 = 1000.0  # Sensor 1
SENSITIVITY2 = 5000.0  # Sensor 2
# ==========================================

plt.ion()
# 2행 1열 서브플롯
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8), sharex=True)
plt.subplots_adjust(hspace=0.3)

# --- 첫 번째 그래프 (Sensor 1) ---
ax1.set_title(f"Sensor 1 Absolute Intensity (Sens: {int(SENSITIVITY1)})")
ax1.set_ylabel("|Intensity|")
ax1.set_ylim(-0.1, 1.2) # 0 ~ 1 범위 (약간 여유)
ax1.grid(True)
ax1.axhline(0, color='black', linewidth=1, linestyle='--')
line1, = ax1.plot([], [], 'b-', label='Sensor 1', linewidth=1.5)
ax1.legend(loc='upper left')

# --- 두 번째 그래프 (Sensor 2) ---
ax2.set_title(f"Sensor 2 Absolute Intensity (Sens: {int(SENSITIVITY2)})")
ax2.set_xlabel("Time Step")
ax2.set_ylabel("|Intensity|")
ax2.set_ylim(-0.1, 1.2) # 0 ~ 1 범위
ax2.grid(True)
ax2.axhline(0, color='black', linewidth=1, linestyle='--')
line2, = ax2.plot([], [], 'r-', label='Sensor 2', linewidth=1.5)
ax2.legend(loc='upper left')

print("\n--- 모니터링 시작 ---")

try:
    while running:
        while ser.in_waiting > 0:
            try:
                line_str = ser.readline().decode('utf-8').strip()
                
                if ',' in line_str:
                    parts = line_str.split(',')
                    if len(parts) >= 2:
                        curr_val1 = int(parts[0])
                        curr_val2 = int(parts[1])
                        
                        int1 = 0.0
                        int2 = 0.0
                        
                        # Sensor 1 계산 (절댓값 적용)
                        if prev_val1 is not None:
                            delta1 = curr_val1 - prev_val1
                            # 🚀 [수정] 절댓값(abs) 사용
                            val1 = abs(delta1) / SENSITIVITY1
                            # 범위 제한 (0 ~ 1.0)
                            int1 = min(1.0, val1)
                        
                        # Sensor 2 계산 (절댓값 적용)
                        if prev_val2 is not None:
                            delta2 = curr_val2 - prev_val2
                            # 🚀 [수정] 절댓값(abs) 사용
                            val2 = abs(delta2) / SENSITIVITY2
                            # 범위 제한 (0 ~ 1.0)
                            int2 = min(1.0, val2)
                        
                        prev_val1 = curr_val1
                        prev_val2 = curr_val2
                        
                        intensity_data1.append(int1)
                        intensity_data2.append(int2)

            except: pass
        
        # 그래프 업데이트
        line1.set_ydata(intensity_data1)
        line1.set_xdata(range(len(intensity_data1)))
        
        line2.set_ydata(intensity_data2)
        line2.set_xdata(range(len(intensity_data2)))
        
        ax1.set_xlim(0, max(len(intensity_data1), 10))
        
        plt.pause(0.02)

finally:
    plt.close()
    if ser.is_open:
        for key, cmds in key_map.items():
            send_cmd(cmds[1]) 
        ser.close()
    print("종료")