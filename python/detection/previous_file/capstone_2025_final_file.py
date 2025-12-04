import cv2
import depthai as dai
import time
import os
import serial
import keyboard
import matplotlib.pyplot as plt
from collections import deque
import csv
from datetime import datetime
import numpy as np

# ==================================================
# 🚨 [핵심 수정] Matplotlib 단축키 충돌 방지
# s키(저장), q키(종료) 등이 그래프 창에서 작동하지 않게 막습니다.
# ==================================================
plt.rcParams['keymap.save'].remove('s') if 's' in plt.rcParams['keymap.save'] else None
plt.rcParams['keymap.quit'].remove('q') if 'q' in plt.rcParams['keymap.quit'] else None
plt.rcParams['keymap.fullscreen'].remove('f') if 'f' in plt.rcParams['keymap.fullscreen'] else None
# ==================================================

# ==================================================
# 1. 설정 및 초기화
# ==================================================

# --- [설정] 아두이노 및 로드셀 ---
PORT = 'COM5'
BAUD_RATE = 115200 
SENSITIVITY1 = 50000.0  # Sensor 1 민감도
SENSITIVITY2 = 50000.0  # Sensor 2 민감도

# --- [설정] 카메라 및 AI 모델 ---
current_folder = os.path.dirname(os.path.abspath(__file__))
model_blob_path = os.path.join(current_folder, "best.blob")

if not os.path.exists(model_blob_path):
    print(f"🚨 오류: '{model_blob_path}' 파일이 없습니다!")
    exit()

INPUT_SIZE = (640, 640)        
NUM_CLASSES = 1
LABEL_MAP = ["Excavator"]

# --- [초기화] 시리얼 통신 ---
try:
    ser = serial.Serial(PORT, BAUD_RATE, timeout=0.05)
    print(f"✅ 포트 {PORT} 연결 성공")
    ser.reset_input_buffer()
    time.sleep(2) 
except Exception as e:
    print(f"🚨 포트 연결 실패: {e}")
    exit()

# --- [초기화] CSV 파일 ---
current_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"integrated_data_{current_time_str}.csv"
csv_file = open(filename, 'w', newline='')
writer = csv.writer(csv_file)
# CSV 헤더: 시간, 센서1, 센서2, 좌표X, 좌표Y, 좌표Z(거리)
writer.writerow(['Time', 'Sensor1_Rel', 'Sensor2_Rel', 'Bucket_X_mm', 'Bucket_Y_mm', 'Bucket_Z_mm']) 

print(f"=== 통합 시스템 시작: {filename} ===")
print("=== 제어: W/S(암), I/K(붐), J/L(버킷) | 종료: 'q' ===")

# ==================================================
# 2. DepthAI 파이프라인 설정 (카메라)
# ==================================================
pipeline = dai.Pipeline()

# RGB 카메라
camRgb = pipeline.create(dai.node.ColorCamera)
camRgb.setPreviewSize(INPUT_SIZE[0], INPUT_SIZE[1])
camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
camRgb.setInterleaved(False)
camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
camRgb.setFps(30)

# 스테레오 Depth
monoLeft = pipeline.create(dai.node.MonoCamera)
monoRight = pipeline.create(dai.node.MonoCamera)
stereo = pipeline.create(dai.node.StereoDepth)

monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
monoLeft.setBoardSocket(dai.CameraBoardSocket.CAM_B)
monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
monoRight.setBoardSocket(dai.CameraBoardSocket.CAM_C)

stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)

monoLeft.out.link(stereo.left)
monoRight.out.link(stereo.right)

# AI 노드 (YOLO Spatial)
try:
    yoloDet = pipeline.create(dai.node.YoloSpatialDetectionNetwork)
except AttributeError:
    print("🚨 오류: depthai 버전 확인 필요.")
    exit()

yoloDet.setBlobPath(model_blob_path)
yoloDet.setConfidenceThreshold(0.5)
yoloDet.setNumClasses(NUM_CLASSES)
yoloDet.setCoordinateSize(4)
yoloDet.setAnchors([])
yoloDet.setAnchorMasks({})
yoloDet.setIouThreshold(0.5)
yoloDet.setDepthLowerThreshold(100)
yoloDet.setDepthUpperThreshold(10000)

camRgb.preview.link(yoloDet.input)
stereo.depth.link(yoloDet.inputDepth)

# 출력 링크
xoutRgb = pipeline.create(dai.node.XLinkOut)
xoutRgb.setStreamName("rgb")
yoloDet.passthrough.link(xoutRgb.input)

xoutDet = pipeline.create(dai.node.XLinkOut)
xoutDet.setStreamName("detections")
yoloDet.out.link(xoutDet.input)

# ==================================================
# 3. 변수 및 그래프 설정
# ==================================================
# 제어 관련
last_sent_cmds = {'boom': None, 'arm': None, 'bucket': None}

# 로드셀 관련
offset1, offset2 = 0, 0
is_calibrated = False
calib_buffer1, calib_buffer2 = [], []
CALIB_SAMPLES = 20

# 비전 데이터 저장용 (로드셀 데이터와 동기화를 위해 전역 변수처럼 사용)
latest_vision_data = {'x': 0, 'y': 0, 'z': 0}

# 그래프 설정
MAX_POINTS = 100
data1 = deque([0]*MAX_POINTS, maxlen=MAX_POINTS)
data2 = deque([0]*MAX_POINTS, maxlen=MAX_POINTS)

plt.ion()
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6, 6), sharex=True)
plt.subplots_adjust(hspace=0.3)

ax1.set_title("Sensor 1 (Arm)")
ax1.set_ylabel("Relative")
ax1.grid(True)
line1, = ax1.plot([], [], 'r-', label='Sensor 1')

ax2.set_title("Sensor 2 (Boom)")
ax2.set_xlabel("Samples")
ax2.set_ylabel("Relative")
ax2.grid(True)
line2, = ax2.plot([], [], 'b-', label='Sensor 2')

# ==================================================
# 4. 메인 실행 루프
# ==================================================
def send_cmd(cmd):
    try: ser.write(cmd.encode())
    except: pass

print("✅ 카메라 및 센서 연결 완료. 루프 시작...")

# USB 속도 문제 방지를 위해 HIGH 모드 권장
with dai.Device(pipeline, maxUsbSpeed=dai.UsbSpeed.HIGH) as device:
    qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
    qDet = device.getOutputQueue(name="detections", maxSize=4, blocking=False)

    start_time = time.time()
    running = True
    last_plot_time = time.time()
    
    try:
        while running:
            # --------------------------------------
            # [A] 카메라 데이터 처리 (Vision)
            # --------------------------------------
            inRgb = qRgb.tryGet() # Non-blocking
            inDet = qDet.tryGet()

            frame = None
            if inRgb is not None:
                frame = inRgb.getCvFrame()

            if inDet is not None:
                detections = inDet.detections
                
                # 탐지된 객체가 있으면 좌표 업데이트
                if len(detections) > 0:
                    # 가장 신뢰도 높은 첫 번째 객체만 사용
                    det = detections[0] 
                    latest_vision_data['x'] = int(det.spatialCoordinates.x)
                    latest_vision_data['y'] = int(det.spatialCoordinates.y)
                    latest_vision_data['z'] = int(det.spatialCoordinates.z)
                else:
                    # 탐지 안 되면 직전 값 유지 or 0 (여기선 0 리셋)
                    latest_vision_data = {'x': 0, 'y': 0, 'z': 0}

                # 화면 그리기
                if frame is not None:
                    for detection in detections:
                        x1 = int(detection.xmin * frame.shape[1])
                        y1 = int(detection.ymin * frame.shape[0])
                        x2 = int(detection.xmax * frame.shape[1])
                        y2 = int(detection.ymax * frame.shape[0])
                        
                        dist_z = int(detection.spatialCoordinates.z)
                        
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(frame, f"Dist: {dist_z}mm", (x1, y1 - 10), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # 카메라 화면 출력
            if frame is not None:
                cv2.imshow("OAK-D Detection", frame)

            # --------------------------------------
            # [B] 키보드 제어 (Control) - Polling 방식
            # --------------------------------------
            # 종료
            if cv2.waitKey(1) == ord('q') or keyboard.is_pressed('q'):
                running = False
                break
            
            # 0점 재설정
            if keyboard.is_pressed('c'):
                is_calibrated = False
                calib_buffer1, calib_buffer2 = [], []
                print("\n[재설정] 0점 다시 잡는 중...")
                time.sleep(0.1)

            # --- 모터 명령 생성 (Polling) ---
            # 붐
            boom_cmd = 'i' if keyboard.is_pressed('i') else ('k' if keyboard.is_pressed('k') else 'I')
            # 암
            arm_cmd = 'w' if keyboard.is_pressed('w') else ('s' if keyboard.is_pressed('s') else 'W')
            # 버킷
            bucket_cmd = 'j' if keyboard.is_pressed('j') else ('l' if keyboard.is_pressed('l') else 'J')

            # 상태가 변했을 때만 전송 (통신 부하 감소)
            if last_sent_cmds['boom'] != boom_cmd:
                send_cmd(boom_cmd)
                last_sent_cmds['boom'] = boom_cmd
            if last_sent_cmds['arm'] != arm_cmd:
                send_cmd(arm_cmd)
                last_sent_cmds['arm'] = arm_cmd
            if last_sent_cmds['bucket'] != bucket_cmd:
                send_cmd(bucket_cmd)
                last_sent_cmds['bucket'] = bucket_cmd

            # --------------------------------------
            # [C] 로드셀 데이터 수신 및 통합 저장 (Logging)
            # --------------------------------------
            while ser.in_waiting > 0:
                try:
                    line_str = ser.readline().decode('utf-8').strip()
                    if ',' in line_str:
                        parts = line_str.split(',')
                        if len(parts) >= 2:
                            raw1 = int(parts[0])
                            raw2 = int(parts[1])

                            # 1. 캘리브레이션
                            if not is_calibrated:
                                if abs(raw1) > 100 and abs(raw2) > 100:
                                    calib_buffer1.append(raw1)
                                    calib_buffer2.append(raw2)
                                if len(calib_buffer1) >= CALIB_SAMPLES:
                                    offset1 = sum(calib_buffer1) / CALIB_SAMPLES
                                    offset2 = sum(calib_buffer2) / CALIB_SAMPLES
                                    is_calibrated = True
                                    print("✅ 0점 설정 완료! 측정 시작.")
                                continue

                            # 2. 데이터 처리 (상대값)
                            rel1 = raw1 - offset1
                            rel2 = raw2 - offset2
                            
                            # 3. [통합 저장] 로드셀 값 + 현재 카메라 좌표
                            t_now = round(time.time() - start_time, 4)
                            writer.writerow([
                                t_now, 
                                rel1, 
                                rel2, 
                                latest_vision_data['x'], 
                                latest_vision_data['y'], 
                                latest_vision_data['z']
                            ])

                            # 4. 그래프용 데이터
                            data1.append(rel1)
                            data2.append(rel2)

                except: pass

            # --------------------------------------
            # [D] 그래프 그리기 (주기 제한)
            # --------------------------------------
            if is_calibrated and (time.time() - last_plot_time > 0.05):
                line1.set_ydata(data1)
                line1.set_xdata(range(len(data1)))
                line2.set_ydata(data2)
                line2.set_xdata(range(len(data2)))
                
                # Auto Scale (값이 없으면 기본값)
                if len(data1) > 0:
                    y1_min, y1_max = min(data1), max(data1)
                    # 여백 주기
                    pad1 = (y1_max - y1_min) * 0.1 if y1_max != y1_min else 100
                    ax1.set_ylim(y1_min - pad1, y1_max + pad1)
                    ax1.set_xlim(0, len(data1))

                if len(data2) > 0:
                    y2_min, y2_max = min(data2), max(data2)
                    pad2 = (y2_max - y2_min) * 0.1 if y2_max != y2_min else 100
                    ax2.set_ylim(y2_min - pad2, y2_max + pad2)
                    ax2.set_xlim(0, len(data2))
                
                plt.pause(0.001)
                last_plot_time = time.time()

    except Exception as e:
        print(f"에러 발생: {e}")

    finally:
        csv_file.close()
        plt.close()
        cv2.destroyAllWindows()
        if ser.is_open:
            # 안전하게 정지 명령 전송
            for _ in range(3):
                send_cmd('I'); send_cmd('W'); send_cmd('J')
                time.sleep(0.01)
            ser.close()
        print(f"프로그램 종료. 데이터 저장됨: {filename}")