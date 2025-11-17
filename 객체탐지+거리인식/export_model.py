from ultralytics import YOLO
import os

# 현재 경로 확인
print(f"현재 작업 경로: {os.getcwd()}")

# 파일 존재 확인
weight_path = 'runs/detect/train/weights/best.pt'
if os.path.exists(weight_path):
    print(f"✓ 파일 찾음: {weight_path}")
else:
    print(f"✗ 파일 없음: {weight_path}")
    # 다른 경로 시도
    weight_path = 'runs\\detect\\train\\weights\\best.pt'
    if os.path.exists(weight_path):
        print(f"✓ 파일 찾음: {weight_path}")

# 모델 로드
print("모델 로딩 중...")
model = YOLO(weight_path)

# OpenVINO로 변환
print("OpenVINO 형식으로 변환 중...")
path = model.export(format='openvino')
print(f"✓ 변환 완료! 저장 위치: {path}")