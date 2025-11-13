import serial
import keyboard
import time

# 아두이노 포트 확인! (COM3, COM4, /dev/ttyACM0 등)
PORT = 'COM3'
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
print("[붐]   : ↑ (내리기) / ↓ (올리기)")
print("[암]   : W (펼치기) / S (접기)")
print("[버킷] : ← (접기) / → (펼치기)")
print("\n(키를 누르는 동안만 동작합니다)")
print("=== 'ESC' 키를 누르면 종료 ===")

# { 키 이름: (눌렸을 때 보낼 명령, 뗐을 때 보낼 명령) }
# 아두이노 코드의 case와 일치해야 함
key_map = {
    # 붐 (정지 명령: '0')
    'up':   ('U', '0'), # 붐 내리기 (Retract)
    'down': ('D', '0'), # 붐 올리기 (Extend)
    
    # 암 (정지 명령: '1')
    'w': ('w', '1'), # 암 펼치기 (Extend)
    's': ('s', '1'), # 암 접기 (Retract)
    
    # 버킷 (정지 명령: '2')
    'left':  ('L', '2'), # 버킷 접기 (Retract)
    'right': ('R', '2'), # 버킷 펼치기 (Extend)
}

def send_cmd(cmd):
    """아두이노로 1바이트 명령 전송"""
    try:
        # print(f"Send: {cmd}") # 디버깅 시 주석 해제
        ser.write(cmd.encode())
    except Exception as e:
        print(f"데이터 전송 실패: {e}")

def on_key_event(event):
    """키보드 이벤트를 처리하여 아두이노로 명령 전송"""
    # 라이브러리가 'up arrow' 대신 'up'으로 이름을 줌
    key = event.name
    
    # 맵에 없는 키는 무시
    if key not in key_map:
        return
        
    # 'key_map'에서 해당 키의 명령 가져오기
    press_cmd, release_cmd = key_map[key]

    if event.event_type == 'down' and not event.is_repeat:
        # 키가 '처음' 눌렸을 때
        send_cmd(press_cmd)
        
    elif event.event_type == 'up':
        # 키를 '뗐을' 때
        send_cmd(release_cmd)

# -----------------
# 메인 실행
# -----------------
# 키보드 이벤트 핸들러 등록
keyboard.hook(on_key_event)

try:
    # 'ESC' 키가 눌릴 때까지 대기
    keyboard.wait('esc')
finally:
    # 종료 시 모든 모터 정지 명령 전송 (안전 장치)
    print("\n종료 중... 모든 액추에이터 정지")
    send_cmd('0') # 붐 정지
    time.sleep(0.01)
    send_cmd('1') # 암 정지
    time.sleep(0.01)
    send_cmd('2') # 버킷 정지
        
    ser.close()
    print("시리얼 포트 종료. 안녕히 가세요.")