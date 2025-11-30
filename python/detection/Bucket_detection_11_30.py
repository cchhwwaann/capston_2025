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

# 거리 측정 범위 (mm 단위)
yoloDet.setDepthLowerThreshold(100) # 100mm (10cm)
yoloDet.setDepthUpperThreshold(10000) # 10000mm (10m)

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
# USB 속도 문제 방지를 위해 HIGH(USB2.0) 모드 권장
with dai.Device(pipeline, maxUsbSpeed=dai.UsbSpeed.HIGH) as device:
    qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
    qDet = device.getOutputQueue(name="detections", maxSize=4, blocking=False)

    print("✅ 실행 시작! (단위: mm)")

    while True:
        inRgb = qRgb.get()
        inDet = qDet.get()

        if inRgb is not None:
            frame = inRgb.getCvFrame()
        
        if inDet is not None:
            detections = inDet.detections
            for detection in detections:
                h, w = frame.shape[:2]
                x1 = int(detection.xmin * w)
                y1 = int(detection.ymin * h)
                x2 = int(detection.xmax * w)
                y2 = int(detection.ymax * h)

                try:
                    label = LABEL_MAP[detection.label]
                except:
                    label = str(detection.label)

                # ★ [수정됨] mm 단위 그대로 사용 (int로 변환하여 소수점 제거)
                pos_x = int(detection.spatialCoordinates.x)
                pos_y = int(detection.spatialCoordinates.y)
                pos_z = int(detection.spatialCoordinates.z)

                # 화면 그리기
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                label_text = f"{label} {int(detection.confidence * 100)}%"
                # mm 단위로 표시
                coord_text = f"X:{pos_x} Y:{pos_y} Z:{pos_z} mm"
                
                cv2.putText(frame, label_text, (x1, y1 - 20), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                cv2.putText(frame, coord_text, (x1, y1 - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                
                print(f"탐지: {label} | 거리(Z): {pos_z}mm")

        cv2.imshow("OAK-D Edge AI (mm)", frame)

        if cv2.waitKey(1) == ord('q'):
            break

cv2.destroyAllWindows()