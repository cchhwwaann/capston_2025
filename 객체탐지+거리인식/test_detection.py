from ultralytics import YOLO
import cv2

# 모델 로드 (.pt 파일 사용)
model = YOLO('runs/detect/train/weights/best.pt')

# 웹캠으로 실시간 탐지
model.predict(source=0, show=True, conf=0.5)