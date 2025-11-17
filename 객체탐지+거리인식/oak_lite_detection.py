from ultralytics import YOLO
import cv2
import time

print("=" * 60)
print("OAK-D Lite - OpenCV 직접 사용 방식")
print("=" * 60)

# YOLO 모델 로드
print("\n[1/3] 모델 로드 중...")
model = YOLO('runs/detect/train/weights/best_openvino_model/')
print("✓ 모델 로드 완료!")

print("\n[2/3] 카메라 검색 중...")
print("사용 가능한 카메라를 찾고 있습니다...\n")

# 0~5번까지 카메라 인덱스 시도
camera_found = False
working_camera_index = -1

for idx in range(6):
    cap = cv2.VideoCapture(idx)
    
    if cap.isOpened():
        ret, test_frame = cap.read()
        
        if ret and test_frame is not None:
            height, width = test_frame.shape[:2]
            print(f"✓ 카메라 {idx} 발견!")
            print(f"  - 해상도: {width}x{height}")
            
            # OAK-D Lite인지 확인 (보통 높은 해상도)
            if width >= 640:
                working_camera_index = idx
                print(f"  - 이 카메라를 사용합니다!")
                camera_found = True
                break
            else:
                print(f"  - 해상도가 너무 낮습니다. 다음 카메라 확인...")
                cap.release()
        else:
            cap.release()

if not camera_found:
    print("\n❌ 사용 가능한 카메라를 찾을 수 없습니다!")
    print("\n해결 방법:")
    print("1. OAK-D Lite USB 연결 확인 (USB 3.0 포트)")
    print("2. Windows 설정 > 개인정보 > 카메라 > 앱의 카메라 액세스 허용")
    print("3. 장치 관리자에서 'Imaging devices' 또는 'Cameras' 확인")
    print("4. 다른 카메라 앱(Zoom, Teams 등) 종료")
    print("5. 컴퓨터 재부팅 후 재시도")
    exit()

# 카메라 설정
print(f"\n[3/3] 카메라 설정 중... (카메라 {working_camera_index})")
cap = cv2.VideoCapture(working_camera_index)

# 해상도 및 FPS 설정
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)

# 실제 설정된 값 확인
actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
actual_fps = int(cap.get(cv2.CAP_PROP_FPS))

print(f"✓ 설정 완료: {actual_width}x{actual_height} @ {actual_fps}fps")
print("\n" + "=" * 60)
print("실행 중... (종료: 'q', 저장: 's', 정보: 'i')")
print("=" * 60 + "\n")

# 메인 루프
frame_count = 0
detection_count = 0
start_time = time.time()
fps = 0
show_info = True

try:
    while True:
        ret, frame = cap.read()
        
        if not ret or frame is None:
            print("⚠ 프레임 읽기 실패... 재시도 중...")
            time.sleep(0.1)
            continue
        
        frame_count += 1
        
        # FPS 계산 (30프레임마다)
        if frame_count % 30 == 0:
            elapsed = time.time() - start_time
            fps = 30 / elapsed if elapsed > 0 else 0
            start_time = time.time()
        
        # YOLO 객체 탐지
        results = model(frame, conf=0.5, verbose=False)
        annotated = results[0].plot()
        
        # 검출 정보
        detections = results[0].boxes
        num_detections = len(detections)
        
        if num_detections > 0:
            detection_count += 1
        
        # 화면에 정보 표시
        if show_info:
            info_y = 30
            cv2.putText(annotated, f"FPS: {fps:.1f}", 
                       (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.7, (0, 255, 0), 2)
            
            info_y += 35
            cv2.putText(annotated, f"Frame: {frame_count}", 
                       (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.6, (0, 255, 0), 2)
            
            info_y += 30
            cv2.putText(annotated, f"Objects: {num_detections}", 
                       (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.6, (0, 255, 0), 2)
            
            info_y += 30
            cv2.putText(annotated, f"Camera: {working_camera_index}", 
                       (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.6, (0, 255, 0), 2)
            
            # 검출된 객체 클래스 표시
            if num_detections > 0:
                info_y += 30
                class_names = [results[0].names[int(box.cls)] for box in detections]
                class_text = ", ".join(class_names[:3])  # 최대 3개만
                if len(class_names) > 3:
                    class_text += "..."
                cv2.putText(annotated, f"Detected: {class_text}", 
                           (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 
                           0.5, (255, 255, 0), 2)
        
        # 화면 표시
        cv2.imshow(f"OAK-D Lite (OpenCV) - Camera {working_camera_index}", annotated)
        
        # 키 입력 처리
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("\n종료 중...")
            break
        elif key == ord('s'):
            filename = f"detection_{frame_count:06d}.jpg"
            cv2.imwrite(filename, annotated)
            print(f"✓ 저장: {filename}")
        elif key == ord('i'):
            show_info = not show_info
            print(f"{'✓ 정보 표시' if show_info else '✓ 정보 숨김'}")

except KeyboardInterrupt:
    print("\n\n⚠ 사용자에 의해 중단됨 (Ctrl+C)")

except Exception as e:
    print(f"\n❌ 에러 발생: {e}")
    import traceback
    traceback.print_exc()

finally:
    # 정리
    cap.release()
    cv2.destroyAllWindows()
    
    print("\n" + "=" * 60)
    print("실행 통계:")
    print("=" * 60)
    print(f"총 처리 프레임: {frame_count}")
    print(f"객체 검출 프레임: {detection_count}")
    if frame_count > 0:
        print(f"검출 비율: {detection_count/frame_count*100:.1f}%")
    print(f"최종 FPS: {fps:.1f}")
    print("=" * 60)
    print("\n✓ 프로그램 종료")