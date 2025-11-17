from ultralytics import YOLO
import subprocess
import os

# 1. 먼저 더 작은 이미지 크기로 ONNX 변환 (호환성 개선)
print("1단계: ONNX 변환 (최적화)...")
model = YOLO('runs/detect/train/weights/best.pt')

# 더 작은 크기로 변환 (OAK 카메라에 맞춤)
onnx_path = model.export(
    format='onnx',
    imgsz=416,  # 또는 320
    simplify=True,  # ONNX 단순화
    opset=12  # OpenVINO와 호환되는 opset
)
print(f"✓ ONNX 완료: {onnx_path}")

# 2. OpenVINO로 변환
print("\n2단계: OpenVINO 변환...")
openvino_path = model.export(format='openvino', imgsz=416)
print(f"✓ OpenVINO 완료: {openvino_path}")