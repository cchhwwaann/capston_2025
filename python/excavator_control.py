import serial
import keyboard
import time

# 아두이노 포트 확인! (COM3, COM4 등)
PORT = 'COM5'
BAUD_RATE = 9600

try:
    ser = serial.Serial(PORT, BAUD_RATE, timeout=0.1)
    print(f"포트 {PORT} 연결 성공. 2초 대기...")
    time.sleep(2) # 아두이노 재부팅 대기
except Exception as e:
    print(f"포트 {PORT} 연결 실패. {e}")
    print("아두이노가 연결되었는지, 포트 번호가 맞는지 확인하세요.")
    exit()

print("=== 굴삭기 제어 (Python) ===")
print("[붐]   : J / N")
print("[암]   : K / M")
print("[버킷] : L / , (쉼표)")
print("\n(키를 누르는 동안만 동작합니다)")
print("=== 'ESC' 키를 누르면 종료 ===")

# { 키 이름: (눌렸을 때 보낼 명령, 뗐을 때 보낼 명령) }
key_map = {
    # 붐 (정지 명령: '0')
    'j': ('j', '0'), # 붐 전진 (임의)
    'n': ('n', '0'), # 붐 후진 (임의)
    
    # 암 (정지 명령: '1')
    'k': ('k', '1'), # 암 전진
    'm': ('m', '1'), # 암 후진
    
    # 버킷 (정지 명령: '2')
    'l': ('l', '2'), # 버킷 전진
    ',': (',', '2'), # 버킷 후진
}

# 키가 현재 "눌려있는" 상태인지 수동으로 추적합니다.
key_pressed_state = {key: False for key in key_map.keys()}


def send_cmd(cmd):
    """아두이노로 1바이트 명령 전송"""
    try:
        # print(f"Send: {cmd}") # 디버깅 시 주석 해제
        ser.write(cmd.encode())
    except Exception as e:
        print(f"데이터 전송 실패: {e}")

def on_key_event(event):
    """키보드 이벤트를 처리하여 아두이노로 명령 전송"""
    key = event.name
    
    if key not in key_map:
        return
        
    press_cmd, release_cmd = key_map[key]

    # .is_repeat 대신 수동으로 상태를 확인
    if event.event_type == 'down':
        if not key_pressed_state[key]:
            send_cmd(press_cmd)        # '눌림' 명령 전송
            key_pressed_state[key] = True  # 상태를 '눌림'으로 변경
            
    elif event.event_type == 'up':
        send_cmd(release_cmd)          # '뗌' (정지) 명령 전송
        key_pressed_state[key] = False # 상태를 '뗌'으로 변경

# -----------------
# 메인 실행
# -----------------
keyboard.hook(on_key_event)

try:
    keyboard.wait('esc')
finally:
    print("\n종료 중... 모든 액추에이터 정지")
    send_cmd('0') # 붐 정지
    time.sleep(0.01)
    send_cmd('1') # 암 정지
    time.sleep(0.01)
    send_cmd('2') # 버킷 정지
        
    ser.close()
    print("시리얼 포트 종료. 안녕히 가세요.")