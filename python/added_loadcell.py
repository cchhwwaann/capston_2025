import serial
import keyboard
import time

# --- (시각화 라이브러리 추가) ---
import matplotlib.pyplot as plt
from collections import deque
# ------------------------------

# 🚨 아두이노 포트 확인!
PORT = 'COM5'
BAUD_RATE = 115200

try:
    ser = serial.Serial(PORT, BAUD_RATE, timeout=0.1)
    print(f"포트 {PORT} 연결 성공. 2초 대기...")
    time.sleep(2) # 아두이노 재부팅 및 Tare() 대기
except Exception as e:
    print(f"포트 {PORT} 연결 실패. {e}")
    exit()

print("=== 굴삭기 제어 및 로드셀 실시간 플로팅 ===")
print("[왼손] 암(Arm) : W (펼침) / S (오므림)")
print("[오른손] 붐(Boom) : I (내림) / K (올림)")
print("         버킷(Bucket): J (접기) / L (펼침)")
print("\n(키를 누르는 동안만 동작합니다)")
print("=== 'ESC' 키를 누르면 종료 ===")

# --- (기존 제어 로직 - 동일) ---
key_map = {
    'i': ('i', 'I'), 'k': ('k', 'K'), # 붐
    'w': ('w', 'W'), 's': ('s', 'S'), # 암
    'j': ('j', 'J'), 'l': ('l', 'L')  # 버킷
}
key_pressed_state = {key: False for key in key_map.keys()}
running = True

def send_cmd(cmd):
    try:
        ser.write(cmd.encode())
    except Exception as e:
        print(f"데이터 전송 실패: {e}")

def on_key_event(event):
    global running
    if event.name == 'esc' and event.event_type == 'down':
        print("\n'esc' 키 입력 감지... 종료 시작")
        running = False
        return
    
    key = event.name
    if key not in key_map: return
    
    press_cmd, release_cmd = key_map[key]

    if event.event_type == 'down':
        if not key_pressed_state[key]:
            send_cmd(press_cmd)
            key_pressed_state[key] = True
    elif event.event_type == 'up':
        send_cmd(release_cmd)
        key_pressed_state[key] = False
# ------------------------------


# --- 1. 실시간 플롯 설정 ---

# (1) 데이터 저장소 설정 (최대 100개 데이터 유지)
MAX_PLOT_POINTS = 100
load_cell_data = deque(maxlen=MAX_PLOT_POINTS)

# (2) 대화형 모드 켜기
plt.ion() 

# (3) 그래프 창(Figure) 및 축(Axes) 생성
fig, ax = plt.subplots()
ax.set_title("실시간 로드셀 데이터")
ax.set_xlabel(f"최근 {MAX_PLOT_POINTS}개 샘플")
ax.set_ylabel("로드셀 Raw 값")

# (4) 업데이트할 빈 선(line) 객체 미리 생성
# (x축은 0~100, y축은 일단 0~1000으로 시작, 나중에 자동조절)
line, = ax.plot([], [], 'r-') # 빨간색 선
ax.set_xlim(0, MAX_PLOT_POINTS)
ax.set_ylim(-1000, 1000) # (임의의 시작 범위)
# ------------------------------


# --- 2. 메인 실행 루프 (수정) ---
keyboard.hook(on_key_event) 
print("\n--- 로드셀 모니터링 및 실시간 플로팅 시작 ---")

try:
    while running:
        new_data_available = False
        try:
            # (1) 아두이노로부터 데이터 읽기 (기존과 동일)
            if ser.in_waiting > 0:
                line_str = ser.readline().decode('utf-8').strip()
                
                if line_str.lstrip('-').isdigit():
                    print(f"  [Load Cell]: {line_str.rjust(10)}", end='\r') 
                    
                    # (2) 읽은 값을 플롯 데이터 저장소(deque)에 추가
                    value = int(line_str)
                    load_cell_data.append(value)
                    new_data_available = True
                    
        except serial.SerialException as se:
            print(f"시리얼 오류: {se}. 종료합니다.")
            running = False
        except Exception as e:
            pass # (디코딩 오류 등 가벼운 오류는 무시)
        

        # (3) 새 데이터가 있을 때만 그래프 업데이트 (효율화)
        if new_data_available:
            # line 객체에 새 데이터(Y축)를 업데이트
            line.set_ydata(load_cell_data)
            # X축 데이터도 길이에 맞춰 0부터 순서대로 업데이트
            line.set_xdata(range(len(load_cell_data)))
            
            # Y축 범위(limits)를 데이터에 맞게 자동 조절
            ax.relim() # 데이터 기준 범위 다시 계산
            ax.autoscale_view(scalex=False, scaley=True) # Y축만 자동 스케일

        # (4) 그래프 창 새로고침 및 GUI 이벤트 처리
        # (time.sleep(0.01) 대신 사용)
        plt.pause(0.01)

    
finally:
    # --- 3. 종료 처리 ---
    plt.ioff() # 대화형 모드 끄기
    plt.close(fig) # 그래프 창 닫기
    
    print("\n\n종료 중... 모든 액추에이터 정지")
    if ser.is_open:
        for key, (press_cmd, release_cmd) in key_map.items():
            send_cmd(release_cmd)
            time.sleep(0.01) 
        ser.close()
    print("시리얼 포트 종료. 안녕히 가세요.")