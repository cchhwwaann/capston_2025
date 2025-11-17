from ultralytics import YOLO

model = YOLO('runs/detect/train/weights/best.pt')
print("클래스 이름:", model.names)
# 예: {0: 'person', 1: 'car', 2: 'bicycle'}