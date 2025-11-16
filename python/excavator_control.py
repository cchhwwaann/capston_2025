import serial
import keyboard
import time

# 🚨 아두이노 포트 확인! (COM3, COM4 등)
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

print("=== 굴삭기 2-Hand 제어 (Python) ===")
print("[왼손] 암(Arm) : W (펼침) / S (오므림)")
print("[오른손] 붐(Boom) : I (내림) / K (올림)")
print("         버킷(Bucket): J (접기) / L (펼침)")
print("\n(키를 누르는 동안만 동작합니다)")
print("=== 'ESC' 키를 누르면 종료 ===")

# { 키 이름: (눌렸을 때 보낼 명령, 뗐을 때 보낼 명령) }
# (명령어가 키보드와 1:1로 일치하도록 수정)
key_map = {
    # 오른손: 붐
    'i': ('i', 'I'), # 'I' (Boom Down) -> Go: 'i', Stop: 'I'
    'k': ('k', 'K'), # 'K' (Boom Up)   -> Go: 'k', Stop: 'K'
    
    # 왼손: 암
    'w': ('w', 'W'), # 'W' (Arm Out)   -> Go: 'w', Stop: 'W'
    's': ('s', 'S'), # 'S' (Arm In)    -> Go: 's', Stop: 'S'
    
    # 오른손: 버킷
    'j': ('j', 'J'), # 'J' (Bucket In)  -> Go: 'j', Stop: 'J'
    'l': ('l', 'L'), # 'L' (Bucket Out) -> Go: 'l', Stop: 'L'
}

# 키가 현재 "눌려있는" 상태인지 수동으로 추적
key_pressed_state = {key: False for key in key_map.keys()}


def send_cmd(cmd):
    """아두이노로 1바이트 명령 전송"""
    try:
        # print(f"Send: {cmd}") # 디버깅 필요시 주석 해제
        ser.write(cmd.encode())
    except Exception as e:
        print(f"데이터 전송 실패: {e}")

def on_key_event(event):
    """키보드 이벤트를 처리하여 아두이노로 명령 전송"""
    key = event.name
    
    if key not in key_map:
        return
        
    press_cmd, release_cmd = key_map[key]

    if event.event_type == 'down':
        if not key_pressed_state[key]:
            send_cmd(press_cmd)
            key_pressed_state[key] = True
            
    elif event.event_type == 'up':
        send_cmd(release_cmd)
        key_pressed_state[key] = False

# -----------------
# 메인 실행
# -----------------
keyboard.hook(on_key_event)

try:
    keyboard.wait('esc')
finally:
    # 종료 시 모든 액추에이터에 '정지' 명령(대문자) 전송
    print("\n종료 중... 모든 액추에이터 정지")
    for key, (press_cmd, release_cmd) in key_map.items():
        send_cmd(release_cmd)
        time.sleep(0.01) # 명령어가 씹히지 않도록 잠시 대기
        
    ser.close()
    print("시리얼 포트 종료. 안녕히 가세요.")