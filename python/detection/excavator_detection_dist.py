import cv2
import depthai as dai
import time
import os

# ==================================================
# 1. 설정 (변환된 blob 파일 정보)
# ==================================================
current_folder = os.path.dirname(os.path.abspath(__file__))
model_blob_path = os.path.join(current_folder, "best.blob")

if not os.path.exists(model_blob_path):
    print(f"🚨 오류: '{model_blob_path}' 파일이 없습니다!")
    exit()

# ★ 모델 변환할 때 입력한 사이즈 (보통 640)
INPUT_SIZE = (640, 640)        
NUM_CLASSES = 1
LABEL_MAP = ["Excavator"]

pipeline = dai.Pipeline()

# ==================================================
# 2. 카메라 노드 설정
# ==================================================
# RGB 카메라
camRgb = pipeline.create(dai.node.ColorCamera)
camRgb.setPreviewSize(INPUT_SIZE[0], INPUT_SIZE[1]) # 이미 여기서 크기를 맞춥니다!
camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
camRgb.setInterleaved(False)
camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
camRgb.setFps(30)

# 스테레오 Depth
monoLeft = pipeline.create(dai.node.MonoCamera)
monoRight = pipeline.create(dai.node.MonoCamera)
stereo = pipeline.create(dai.node.StereoDepth)

monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
monoLeft.setBoardSocket(dai.CameraBoardSocket.CAM_B) # LEFT
monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
monoRight.setBoardSocket(dai.CameraBoardSocket.CAM_C) # RIGHT

# Depth 설정
stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A) # RGB와 정렬

monoLeft.out.link(stereo.left)
monoRight.out.link(stereo.right)

# ==================================================
# 3. Edge AI 노드 설정 (YOLO Spatial)
# ==================================================
try:
    yoloDet = pipeline.create(dai.node.YoloSpatialDetectionNetwork)
except AttributeError:
    print("🚨 오류: depthai 버전을 확인해주세요.")
    exit()

yoloDet.setBlobPath(model_blob_path)
yoloDet.setConfidenceThreshold(0.5)

# 🚨 [삭제함] yoloDet.setInputSize(INPUT_SIZE[0], INPUT_SIZE[1]) 
# -> 이 줄이 에러의 원인이었습니다. 이미 camRgb.setPreviewSize에서 처리되므로 필요 없습니다.

# YOLO 설정
yoloDet.setNumClasses(NUM_CLASSES)
yoloDet.setCoordinateSize(4)
yoloDet.setAnchors([])
yoloDet.setAnchorMasks({})
yoloDet.setIouThreshold(0.5)

# 거리 측정 설정
yoloDet.setDepthLowerThreshold(100)
yoloDet.setDepthUpperThreshold(10000)

# 연결
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
                # 좌표 변환
                h, w = frame.shape[:2]
                x1 = int(detection.xmin * w)
                y1 = int(detection.ymin * h)
                x2 = int(detection.xmax * w)
                y2 = int(detection.ymax * h)

                try:
                    label = LABEL_MAP[detection.label]
                except:
                    label = str(detection.label)

                # 거리 정보 (m 단위)
                dist_z = detection.spatialCoordinates.z / 1000.0

                # 그리기
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"{label} {dist_z:.2f}m", (x1, y1 - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                print(f"탐지: {label} | 거리: {dist_z:.2f}m")

        cv2.imshow("OAK-D Edge AI", frame)

        if cv2.waitKey(1) == ord('q'):
            break

cv2.destroyAllWindows()