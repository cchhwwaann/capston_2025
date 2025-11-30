import cv2
import depthai as dai
import time
import os

# ==================================================
# 1. 설정
# ==================================================
current_folder = os.path.dirname(os.path.abspath(__file__))
model_blob_path = os.path.join(current_folder, "best.blob")

if not os.path.exists(model_blob_path):
    print(f"🚨 오류: '{model_blob_path}' 파일이 없습니다!")
    exit()

INPUT_SIZE = (640, 640)        
NUM_CLASSES = 1
LABEL_MAP = ["Excavator"]

pipeline = dai.Pipeline()

# ==================================================
# 2. 카메라 노드 설정
# ==================================================
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

# ==================================================
# 3. Edge AI 노드 설정
# ==================================================
try:
    yoloDet = pipeline.create(dai.node.YoloSpatialDetectionNetwork)
except AttributeError:
    print("🚨 오류: depthai 버전을 확인해주세요.")
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

# ==================================================
# 4. 출력 설정
# ==================================================
xoutRgb = pipeline.create(dai.node.XLinkOut)
xoutRgb.setStreamName("rgb")
yoloDet.passthrough.link(xoutRgb.input)

xoutDet = pipeline.create(dai.node.XLinkOut)
xoutDet.setStreamName("detections")
yoloDet.out.link(xoutDet.input)

# ==================================================
# 5. 실행
# ==================================================
print("카메라 연결 중...")
with dai.Device(pipeline) as device:
    qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
    qDet = device.getOutputQueue(name="detections", maxSize=4, blocking=False)

    print("✅ 실행 시작! (종료: q)")

    while True:
        inRgb = qRgb.get()
        inDet = qDet.get()

        if inRgb is not None:
            frame = inRgb.getCvFrame()
        
        if inDet is not None:
            detections = inDet.detections
            for detection in detections:
                # 1. 2D 박스 좌표 변환
                h, w = frame.shape[:2]
                x1 = int(detection.xmin * w)
                y1 = int(detection.ymin * h)
                x2 = int(detection.xmax * w)
                y2 = int(detection.ymax * h)

                try:
                    label = LABEL_MAP[detection.label]
                except:
                    label = str(detection.label)

                # 2. [핵심] 3D 공간 좌표 가져오기 (단위: mm -> m 변환)
                # spatialCoordinates 객체에 x, y, z 값이 다 들어있습니다.
                # X: 카메라 기준 오른쪽(+)/왼쪽(-)
                # Y: 카메라 기준 아래쪽(+)/위쪽(-)
                # Z: 카메라 기준 전방 거리(+)
                pos_x = detection.spatialCoordinates.x / 1000.0
                pos_y = detection.spatialCoordinates.y / 1000.0
                pos_z = detection.spatialCoordinates.z / 1000.0

                # 3. 화면에 그리기
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                # 라벨 표시
                label_text = f"{label} {int(detection.confidence * 100)}%"
                cv2.putText(frame, label_text, (x1, y1 - 20), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # 3D 좌표 표시 (노란색)
                coord_text = f"X:{pos_x:.1f}m Y:{pos_y:.1f}m Z:{pos_z:.1f}m"
                cv2.putText(frame, coord_text, (x1, y1 - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                
                # 터미널 출력
                # print(f"탐지: {label} | 위치: (X:{pos_x:.2f}, Y:{pos_y:.2f}, Z:{pos_z:.2f})")

        cv2.imshow("OAK-D 3D Coordinates", frame)

        if cv2.waitKey(1) == ord('q'):
            break

cv2.destroyAllWindows()