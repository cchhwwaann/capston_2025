import serial
import keyboard
import time
import matplotlib.pyplot as plt
from collections import deque
import csv
from datetime import datetime

# 🚨 아두이노 포트 확인
PORT = 'COM5'
BAUD_RATE = 115200 

try:
    ser = serial.Serial(PORT, BAUD_RATE, timeout=0.05)
    print(f"포트 {PORT} 연결 성공 (속도: {BAUD_RATE})")
    ser.reset_input_buffer()
    time.sleep(2) 
except Exception as e:
    print(f"포트 연결 실패: {e}")
    exit()

# CSV 파일 생성
current_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"sensor_data_{current_time_str}.csv"
csv_file = open(filename, 'w', newline='')
writer = csv.writer(csv_file)
writer.writerow(['Time', 'Sensor1_Rel', 'Sensor2_Rel']) 

print(f"=== 데이터 저장 시작: {filename} ===")
print("=== [안전모드] 키를 떼면 즉시 정지합니다 ===")
print("=== 제어 키: W/S(암), I/K(붐), J/L(버킷) ===")
print("=== 'c': 0점 재설정, 'q': 저장 후 종료 ===")

# --- 제어 설정 ---
# 키 매핑: {키: (눌렀을때_명령, 뗐을때_명령)}
key_map = {
    'i': ('i', 'I'), 'k': ('k', 'K'),
    'w': ('w', 'W'), 's': ('s', 'S'),
    'j': ('j', 'J'), 'l': ('l', 'L')
}

# 각 액추에이터의 현재 상태 추적 (명령 중복 전송 방지용)
# Key: 액추에이터 그룹(붐/암/버킷), Value: 현재 보낸 명령
last_sent_cmds = {
    'boom': None,   # I, K
    'arm': None,    # W, S
    'bucket': None  # J, L
}

def send_cmd(cmd):
    try:
        ser.write(cmd.encode())
    except: pass

# --- 캘리브레이션 변수 ---
offset1 = 0
offset2 = 0
is_calibrated = False
calib_buffer1 = []
calib_buffer2 = []
CALIB_SAMPLES = 20 

# --- 플롯 설정 ---
MAX_POINTS = 100
data1 = deque([0]*MAX_POINTS, maxlen=MAX_POINTS)
data2 = deque([0]*MAX_POINTS, maxlen=MAX_POINTS)

plt.ion()
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8), sharex=True)
plt.subplots_adjust(hspace=0.3) 

# Sensor 1
ax1.set_title("Sensor 1 (Arm) - Auto Scaled")
ax1.set_ylabel("Relative Force")
ax1.grid(True)
ax1.axhline(0, color='black', linewidth=1, linestyle='--')
line1, = ax1.plot([], [], 'r-', label='Sensor 1', linewidth=1.5)
ax1.legend(loc='upper left')

# Sensor 2
ax2.set_title("Sensor 2 (Boom) - Auto Scaled")
ax2.set_xlabel("Recent Samples")
ax2.set_ylabel("Relative Force")
ax2.grid(True)
ax2.axhline(0, color='black', linewidth=1, linestyle='--')
line2, = ax2.plot([], [], 'b-', label='Sensor 2', linewidth=1.5)
ax2.legend(loc='upper left')

start_time = time.time()
running = True
last_plot_time = time.time()

print("\n--- 초기 0점 조절 중... 잠시만 기다려주세요 ---")

try:
    while running:
        # ==========================================
        # 1. [핵심 수정] 상태 기반 키보드 제어 (Polling)
        # ==========================================
        if keyboard.is_pressed('q'):
            running = False
            break
        
        if keyboard.is_pressed('c'):
            print("\n[재설정] 0점을 다시 잡습니다...")
            is_calibrated = False
            calib_buffer1 = []
            calib_buffer2 = []
            time.sleep(0.2) # 채터링 방지

        # --- 붐 제어 (I/K) ---
        boom_cmd = None
        if keyboard.is_pressed('i'): boom_cmd = 'i'
        elif keyboard.is_pressed('k'): boom_cmd = 'k'
        else: boom_cmd = 'I' # 아무것도 안 누르면 정지 명령
        
        if last_sent_cmds['boom'] != boom_cmd:
            send_cmd(boom_cmd)
            last_sent_cmds['boom'] = boom_cmd

        # --- 암 제어 (W/S) ---
        arm_cmd = None
        if keyboard.is_pressed('w'): arm_cmd = 'w'
        elif keyboard.is_pressed('s'): arm_cmd = 's'
        else: arm_cmd = 'W' 
        
        if last_sent_cmds['arm'] != arm_cmd:
            send_cmd(arm_cmd)
            last_sent_cmds['arm'] = arm_cmd

        # --- 버킷 제어 (J/L) ---
        bucket_cmd = None
        if keyboard.is_pressed('j'): bucket_cmd = 'j'
        elif keyboard.is_pressed('l'): bucket_cmd = 'l'
        else: bucket_cmd = 'J'
        
        if last_sent_cmds['bucket'] != bucket_cmd:
            send_cmd(bucket_cmd)
            last_sent_cmds['bucket'] = bucket_cmd


        # ==========================================
        # 2. 데이터 수신 및 처리
        # ==========================================
        while ser.in_waiting > 0:
            try:
                line_str = ser.readline().decode('utf-8').strip()
                
                if ',' in line_str:
                    parts = line_str.split(',')
                    if len(parts) >= 2:
                        raw1 = int(parts[0])
                        raw2 = int(parts[1])
                        
                        # [캘리브레이션]
                        if not is_calibrated:
                            if abs(raw1) > 100 and abs(raw2) > 100:
                                calib_buffer1.append(raw1)
                                calib_buffer2.append(raw2)
                            
                            if len(calib_buffer1) >= CALIB_SAMPLES:
                                offset1 = sum(calib_buffer1) / CALIB_SAMPLES
                                offset2 = sum(calib_buffer2) / CALIB_SAMPLES
                                is_calibrated = True
                                print(f"0점 설정 완료! (Offset: {int(offset1)}, {int(offset2)})")
                            continue

                        # [데이터 처리] (현재값 - 오프셋)
                        rel1 = raw1 - offset1
                        rel2 = raw2 - offset2
                        
                        # 저장
                        current_time = time.time() - start_time
                        writer.writerow([round(current_time, 4), rel1, rel2])

                        # 플롯 데이터 업데이트
                        data1.append(rel1)
                        data2.append(rel2)

            except: pass
        
        # ==========================================
        # 3. 그래프 그리기 (속도 제한 적용)
        # ==========================================
        # 너무 자주 그리면 제어 반응이 느려지므로 0.05초마다 한 번만 갱신
        if is_calibrated and (time.time() - last_plot_time > 0.05):
            line1.set_ydata(data1)
            line1.set_xdata(range(len(data1)))
            
            line2.set_ydata(data2)
            line2.set_xdata(range(len(data2)))
            
            # Smart Auto Scale
            if len(data1) > 0:
                y1_min, y1_max = min(data1), max(data1)
                m1 = (y1_max - y1_min) * 0.1 if y1_max != y1_min else 100
                ax1.set_ylim(y1_min - m1, y1_max + m1)
                ax1.set_xlim(0, len(data1))

            if len(data2) > 0:
                y2_min, y2_max = min(data2), max(data2)
                m2 = (y2_max - y2_min) * 0.1 if y2_max != y2_min else 100
                ax2.set_ylim(y2_min - m2, y2_max + m2)
                ax2.set_xlim(0, len(data2))
            
            plt.pause(0.001) # 아주 짧게
            last_plot_time = time.time()

finally:
    csv_file.close() 
    plt.close()
    if ser.is_open:
        # 안전하게 모든 정지 명령 전송
        stop_cmds = ['I', 'K', 'W', 'S', 'J', 'L']
        for cmd in stop_cmds:
            ser.write(cmd.encode())
            time.sleep(0.01)
        ser.close()
    print(f"\n종료되었습니다. '{filename}' 확인.")