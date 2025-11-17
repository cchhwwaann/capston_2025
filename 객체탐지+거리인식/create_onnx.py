from ultralytics import YOLO

# 모델 로드
model = YOLO('runs/detect/train/weights/best.pt')

# 먼저 ONNX로 변환
print("ONNX 파일 생성 중...")
onnx_path = model.export(format='onnx', imgsz=416)
print(f"✓ ONNX 파일 생성 완료: {onnx_path}")