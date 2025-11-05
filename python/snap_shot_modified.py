#snap_shot_modified.py

import cv2
import depthai as dai
import time
from pathlib import Path  # <--- 폴더 관리를 위해 추가

print("OAK 카메라 스냅샷 코드 (v3 API) - YOLOv8 데이터셋 저장용")
print("프리뷰 창에서 'c' 키를 누르면 스냅샷이 저장됩니다.")
print("'q' 키를 누르면 종료됩니다.")

# ---------------------------------------------------
# [새 설정] 이미지를 저장할 폴더 경로
# 스크립트가 있는 위치에 "yolov8_dataset/images" 폴더를 만듭니다.
OUTPUT_DIR = Path("yolov8_dataset") / "images"

# [새 설정] 폴더가 없으면 자동으로 생성
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print(f"✅ 스냅샷 저장 폴더: {OUTPUT_DIR.resolve()}")
# ---------------------------------------------------


# 1. 파이프라인 생성
pipeline = dai.Pipeline()

# 2. 카메라 노드 생성
cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)

# 3. 프리뷰용 출력 설정 (1080x720)
previewOut = cam.requestOutput((1080, 720), type=dai.ImgFrame.Type.NV12)
qPreview = previewOut.createOutputQueue(maxSize=4, blocking=False)

# 4. 스냅샷(고해상도)용 출력 설정 (센서 최대 해상도)
stillOut = cam.requestFullResolutionOutput()
qStill = stillOut.createOutputQueue(maxSize=4, blocking=False)


# 5. 파이프라인 시작
pipeline.start()

# 스냅샷을 저장할 최신 고해상도 프레임을 담을 변수
latestStillFrame = None
snapshot_counter = 0  # <--- 저장된 이미지 카운터

while pipeline.isRunning():
    # 프리뷰 큐에서 프레임 가져오기
    previewIn = qPreview.get()
    cv2.imshow("Preview", previewIn.getCvFrame())

    # 스냅샷(고해상도) 큐에서 프레임 가져오기 (논블로킹)
    stillIn = qStill.tryGet()
    if stillIn is not None:
        latestStillFrame = stillIn

    key = cv2.waitKey(1)
    if key == ord('q'):
        pipeline.stop() 
        break
    elif key == ord('c'):
        if latestStillFrame is not None:
            # 파일 이름 생성 (예: bucket_0001.png)
            # 시간을 기준으로 하는 것보다 순차적인 번호가 관리하기 좋습니다.
            snapshot_counter += 1
            filename = OUTPUT_DIR / f"bucket_{snapshot_counter:04d}.png"
            
            # getCvFrame()을 호출하여 BGR 포맷으로 변환
            frame_to_save = latestStillFrame.getCvFrame()
            
            # 해상도 정보 출력
            h, w, _ = frame_to_save.shape
            print(f"[{w}x{h}] 스냅샷 저장 중... -> {filename.name}")
            
            # [수정됨] OpenCV가 Path 객체를 인식하도록 str()로 변환
            cv2.imwrite(str(filename), frame_to_save)
            print(f"저장 완료: {filename.name} (총 {snapshot_counter}장)")
        else:
            print("아직 고해상도 프레임을 받지 못했습니다. 잠시 후 다시 시도하세요.")

# 6. 종료 처리
pipeline.wait()
cv2.destroyAllWindows()
print("파이프라인이 중지되었습니다.")