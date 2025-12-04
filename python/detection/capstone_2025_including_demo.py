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

# 🚨 [설정] Matplotlib 단축키 해제
plt.rcParams['keymap.save'].remove('s') if 's' in plt.rcParams['keymap.save'] else None
plt.rcParams['keymap.quit'].remove('q') if 'q' in plt.rcParams['keymap.quit'] else None
plt.rcParams['keymap.fullscreen'].remove('f') if 'f' in plt.rcParams['keymap.fullscreen'] else None

# ==================================================
# 1. 설정 및 방향 반전
# ==================================================
PORT = 'COM5'
BAUD_RATE = 115200 
SENSITIVITY1 = 50000.0
SENSITIVITY2 = 50000.0

# 🔄 W/S 키 방향 반전 유지
key_map = {
    'i': ('i', 'I'), 'k': ('k', 'K'), # 붐
    'w': ('s', 'S'), 's': ('w', 'W'), # 암 (반전됨)
    'j': ('j', 'J'), 'l': ('l', 'L')  # 버킷
}

# 🎬 [시연 시나리오]
DEMO_SEQUENCE = [
    {'name': "1. 암 펼치기 (5초)", 'cmd': 's', 'stop': 'S', 'duration': 3.0},
    {'name': "4. 붐 올리기 (3초)",  'cmd': 'k', 'stop': 'K', 'duration': 2.0},
    {'name': "3. 암 오므리기 (5초)", 'cmd': 'w', 'stop': 'W', 'duration': 2.0},
    {'name': "2. 붐 내리기 (3초)", 'cmd': 'i', 'stop': 'I', 'duration': 2.0},
    {'name': "5. 대기 (1초)",      'cmd': None, 'stop': None, 'duration': 0.5},
]

# --- 파일 및 카메라 설정 ---
current_folder = os.path.dirname(os.path.abspath(__file__))
model_blob_path = os.path.join(current_folder, "best.blob")

if not os.path.exists(model_blob_path):
    print(f"🚨 오류: '{model_blob_path}' 파일 없음!")
    exit()

INPUT_SIZE = (640, 640)        
NUM_CLASSES = 1
LABEL_MAP = ["Excavator"]

try:
    ser = serial.Serial(PORT, BAUD_RATE, timeout=0.05)
    print(f"✅ 포트 {PORT} 연결 성공")
    ser.reset_input_buffer()
    time.sleep(2) 
except Exception as e:
    print(f"🚨 포트 연결 실패: {e}")
    exit()

current_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"demo_final_{current_time_str}.csv"
csv_file = open(filename, 'w', newline='')
writer = csv.writer(csv_file)
# CSV 헤더 (저장되는 파일에는 구분용으로 남겨두거나 원하시면 수정 가능)
writer.writerow(['Time', 'Boom_Top_Rel', 'Boom_Bottom_Rel', 'Bucket_X', 'Bucket_Y', 'Bucket_Z']) 

print(f"=== 통합 시스템 준비 완료 ===")
print("=== [1]: 시연 시작 / [q]: 종료 / [W/S]: 암 제어(반전됨) ===")

# ==================================================
# 2. DepthAI 파이프라인
# ==================================================
pipeline = dai.Pipeline()

camRgb = pipeline.create(dai.node.ColorCamera)
camRgb.setPreviewSize(INPUT_SIZE[0], INPUT_SIZE[1])
camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
camRgb.setInterleaved(False)
camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
camRgb.setFps(30)

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

try:
    yoloDet = pipeline.create(dai.node.YoloSpatialDetectionNetwork)
except AttributeError:
    print("🚨 오류: depthai 버전 확인.")
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

xoutRgb = pipeline.create(dai.node.XLinkOut)
xoutRgb.setStreamName("rgb")
yoloDet.passthrough.link(xoutRgb.input)

xoutDet = pipeline.create(dai.node.XLinkOut)
xoutDet.setStreamName("detections")
yoloDet.out.link(xoutDet.input)

# ==================================================
# 3. 변수 및 그래프 (제목 수정 완료)
# ==================================================
last_sent_cmds = {'boom': None, 'arm': None, 'bucket': None}
offset1, offset2 = 0, 0
is_calibrated = False
calib_buffer1, calib_buffer2 = [], []
CALIB_SAMPLES = 20
latest_vision_data = {'x': 0, 'y': 0, 'z': 0}

MAX_POINTS = 100
data1 = deque([0]*MAX_POINTS, maxlen=MAX_POINTS)
data2 = deque([0]*MAX_POINTS, maxlen=MAX_POINTS)

plt.ion()
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6, 6), sharex=True)
plt.subplots_adjust(hspace=0.3)

# 🎨 [수정] 제목 깔끔하게 변경
ax1.set_title("Boom Top")
ax1.set_ylabel("Relative")
ax1.grid(True)
line1, = ax1.plot([], [], 'b-', label='Boom Top') # Blue

# 🎨 [수정] 제목 깔끔하게 변경
ax2.set_title("Boom Bottom")
ax2.set_xlabel("Samples")
ax2.set_ylabel("Relative")
ax2.grid(True)
line2, = ax2.plot([], [], 'r-', label='Boom Bottom') # Red

# ==================================================
# 4. 메인 루프
# ==================================================
def send_cmd(cmd):
    try: ser.write(cmd.encode())
    except: pass

demo_running = False
demo_step_idx = 0
step_start_time = 0

with dai.Device(pipeline, maxUsbSpeed=dai.UsbSpeed.HIGH) as device:
    qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
    qDet = device.getOutputQueue(name="detections", maxSize=4, blocking=False)

    start_time = time.time()
    running = True
    last_plot_time = time.time()
    
    try:
        while running:
            # --- [A] 카메라 ---
            inRgb = qRgb.tryGet()
            inDet = qDet.tryGet()

            frame = None
            if inRgb is not None:
                frame = inRgb.getCvFrame()

            if inDet is not None:
                detections = inDet.detections
                if len(detections) > 0:
                    det = detections[0]
                    latest_vision_data['x'] = int(det.spatialCoordinates.x)
                    latest_vision_data['y'] = int(det.spatialCoordinates.y)
                    latest_vision_data['z'] = int(det.spatialCoordinates.z)
                else:
                    latest_vision_data = {'x': 0, 'y': 0, 'z': 0}

                if frame is not None:
                    for detection in detections:
                        x1 = int(detection.xmin * frame.shape[1])
                        y1 = int(detection.ymin * frame.shape[0])
                        x2 = int(detection.xmax * frame.shape[1])
                        y2 = int(detection.ymax * frame.shape[0])
                        
                        pos_x = int(detection.spatialCoordinates.x)
                        pos_y = int(detection.spatialCoordinates.y)
                        pos_z = int(detection.spatialCoordinates.z)
                        confidence = int(detection.confidence * 100)
                        
                        try: label = LABEL_MAP[detection.label]
                        except: label = str(detection.label)

                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        
                        label_text = f"{label} {confidence}%"
                        cv2.putText(frame, label_text, (x1, y1 - 20), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        
                        coord_text = f"X:{pos_x} Y:{pos_y} Z:{pos_z} mm"
                        cv2.putText(frame, coord_text, (x1, y1 - 5), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            
            if frame is not None:
                status = f"MODE: DEMO ({DEMO_SEQUENCE[demo_step_idx]['name']})" if demo_running else "MODE: MANUAL"
                col = (0, 0, 255) if demo_running else (0, 255, 255)
                cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
                cv2.imshow("OAK-D Integrated", frame)

            # --- [B] 제어 로직 ---
            if cv2.waitKey(1) == ord('q') or keyboard.is_pressed('q'):
                running = False
                break
            
            if keyboard.is_pressed('1') and not demo_running:
                print("\n🚀 시연 모드 시작!")
                demo_running = True
                demo_step_idx = 0
                step_start_time = time.time()
                is_calibrated = False 
                calib_buffer1, calib_buffer2 = [], []

            # --- 시연 ---
            if demo_running:
                if not is_calibrated: pass 
                else:
                    if demo_step_idx < len(DEMO_SEQUENCE):
                        step = DEMO_SEQUENCE[demo_step_idx]
                        elapsed = time.time() - step_start_time
                        
                        if step['cmd'] is not None: send_cmd(step['cmd'])
                        
                        if elapsed > step['duration']:
                            if step['stop'] is not None: send_cmd(step['stop'])
                            demo_step_idx += 1
                            step_start_time = time.time()
                    else:
                        print("✅ 시연 종료.")
                        demo_running = False
                        send_cmd('I'); send_cmd('W'); send_cmd('J')

            # --- 수동 ---
            else:
                if keyboard.is_pressed('c'):
                    is_calibrated = False
                    calib_buffer1, calib_buffer2 = [], []
                    print("0점 재설정...")
                    time.sleep(0.1)

                boom_cmd = 'i' if keyboard.is_pressed('i') else ('k' if keyboard.is_pressed('k') else 'I')
                arm_cmd = 's' if keyboard.is_pressed('w') else ('w' if keyboard.is_pressed('s') else 'W')
                bucket_cmd = 'j' if keyboard.is_pressed('j') else ('l' if keyboard.is_pressed('l') else 'J')

                if last_sent_cmds['boom'] != boom_cmd:
                    send_cmd(boom_cmd); last_sent_cmds['boom'] = boom_cmd
                if last_sent_cmds['arm'] != arm_cmd:
                    send_cmd(arm_cmd); last_sent_cmds['arm'] = arm_cmd
                if last_sent_cmds['bucket'] != bucket_cmd:
                    send_cmd(bucket_cmd); last_sent_cmds['bucket'] = bucket_cmd

            # --- [C] 로드셀 & 저장 ---
            while ser.in_waiting > 0:
                try:
                    line = ser.readline().decode().strip()
                    if ',' in line:
                        parts = line.split(',')
                        if len(parts) >= 2:
                            r1 = int(parts[0]) # Sensor 1
                            r2 = int(parts[1]) # Sensor 2

                            if not is_calibrated:
                                if abs(r1)>100 and abs(r2)>100:
                                    calib_buffer1.append(r1); calib_buffer2.append(r2)
                                if len(calib_buffer1) >= CALIB_SAMPLES:
                                    offset1 = sum(calib_buffer1)/CALIB_SAMPLES
                                    offset2 = sum(calib_buffer2)/CALIB_SAMPLES
                                    is_calibrated = True
                                    print("0점 완료.")
                                continue
                            
                            rel1 = r1 - offset1
                            rel2 = r2 - offset2
                            
                            t_now = round(time.time() - start_time, 4)
                            writer.writerow([t_now, rel1, rel2, latest_vision_data['x'], latest_vision_data['y'], latest_vision_data['z']])
                            
                            data1.append(rel1) 
                            data2.append(rel2)
                except: pass

            # --- [D] 그래프 ---
            if is_calibrated and (time.time() - last_plot_time > 0.05):
                # Line 1 (Top Plot) -> Sensor 1 (Blue)
                line1.set_ydata(data1) 
                line1.set_xdata(range(len(data1)))
                
                # Line 2 (Bottom Plot) -> Sensor 2 (Red)
                line2.set_ydata(data2)
                line2.set_xdata(range(len(data2)))
                
                # Scale Graph 1 (Sensor 1)
                if len(data1) > 0:
                    ax1.set_ylim(min(data1)-100, max(data1)+100); ax1.set_xlim(0, len(data1))
                # Scale Graph 2 (Sensor 2)
                if len(data2) > 0:
                    ax2.set_ylim(min(data2)-100, max(data2)+100); ax2.set_xlim(0, len(data2))
                
                plt.pause(0.001)
                last_plot_time = time.time()

    except Exception as e:
        print(f"에러: {e}")

    finally:
        csv_file.close()
        plt.close()
        cv2.destroyAllWindows()
        if ser.is_open:
            for _ in range(3): send_cmd('I'); send_cmd('W'); send_cmd('J'); time.sleep(0.01)
            ser.close()
        print(f"종료. {filename} 저장됨.")