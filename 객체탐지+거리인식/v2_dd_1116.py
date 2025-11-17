import depthai as dai
import cv2
import numpy as np
from pathlib import Path
import time

# ========== 설정 ==========
BLOB_PATH = "runs/detect/train/weights/best_openvino_model/best.blob"
CLASS_NAMES = {0: "bucket"}
INPUT_SIZE = (416, 416)
CONF_THRESHOLD = 0.25
IOU_THRESHOLD = 0.45

# 성능 최적화 설정
DISPLAY_WIDTH = 416   # 화면 크기 축소 (원래 640)
DISPLAY_HEIGHT = 416
PROCESS_EVERY_N_FRAMES = 2  # N프레임마다 1번만 처리 (1=모든 프레임, 2=절반)
DEPTH_EVERY_N_FRAMES = 3    # Depth는 더 적게 업데이트

# ========== YOLOv8 후처리 ==========
def decode_yolov8_raw(output, conf_threshold=0.25):
    """YOLOv8 raw 출력 디코딩 (최적화)"""
    if len(output.shape) == 3:
        predictions = output[0].T
    elif len(output.shape) == 2:
        predictions = output.T
    else:
        predictions = output
    
    boxes = predictions[:, :4]
    
    if predictions.shape[1] > 5:
        confidences = np.max(predictions[:, 4:], axis=1)
        class_ids = np.argmax(predictions[:, 4:], axis=1)
    else:
        confidences = predictions[:, 4]
        class_ids = np.zeros(len(confidences), dtype=int)
    
    mask = confidences > conf_threshold
    return boxes[mask], confidences[mask], class_ids[mask]

def xywh2xyxy_yolov8(boxes, img_width, img_height, input_width=416, input_height=416):
    """YOLOv8 좌표 변환 (최적화)"""
    if len(boxes) == 0:
        return np.array([])
    
    scale_x = img_width / input_width
    scale_y = img_height / input_height
    
    x_center = boxes[:, 0] * scale_x
    y_center = boxes[:, 1] * scale_y
    width = boxes[:, 2] * scale_x
    height = boxes[:, 3] * scale_y
    
    x1 = np.clip(x_center - width / 2, 0, img_width)
    y1 = np.clip(y_center - height / 2, 0, img_height)
    x2 = np.clip(x_center + width / 2, 0, img_width)
    y2 = np.clip(y_center + height / 2, 0, img_height)
    
    return np.stack([x1, y1, x2, y2], axis=1)

def nms_fast(boxes, scores, iou_threshold=0.45):
    """빠른 NMS (cv2 사용)"""
    if len(boxes) == 0:
        return []
    
    # OpenCV의 NMS 사용 (C++로 구현되어 매우 빠름)
    indices = cv2.dnn.NMSBoxes(
        boxes.tolist(),
        scores.tolist(),
        score_threshold=0,
        nms_threshold=iou_threshold
    )
    
    if len(indices) > 0:
        return indices.flatten().tolist()
    return []

# ========== 3D 좌표 계산 (최적화) ==========
def get_3d_coordinates_fast(depth_frame, x_pixel, y_pixel, rgb_shape):
    """빠른 3D 좌표 계산 (윈도우 크기 축소)"""
    depth_h, depth_w = depth_frame.shape[:2]
    rgb_h, rgb_w = rgb_shape[:2]
    
    x_depth = int(x_pixel * depth_w / rgb_w)
    y_depth = int(y_pixel * depth_h / rgb_h)
    
    x = int(np.clip(x_depth, 0, depth_w - 1))
    y = int(np.clip(y_depth, 0, depth_h - 1))
    
    # 3x3 윈도우로 축소 (원래 5x5)
    window_size = 3
    x_start = max(0, x - window_size // 2)
    x_end = min(depth_w, x + window_size // 2 + 1)
    y_start = max(0, y - window_size // 2)
    y_end = min(depth_h, y + window_size // 2 + 1)
    
    depth_window = depth_frame[y_start:y_end, x_start:x_end]
    valid_depths = depth_window[depth_window > 0]
    
    if len(valid_depths) == 0:
        return None
    
    # 평균 사용 (중앙값보다 빠름)
    depth_mm = np.mean(valid_depths)
    
    focal_length = 440
    cx = depth_w / 2
    cy = depth_h / 2
    
    z = depth_mm
    x_3d = (x - cx) * z / focal_length
    y_3d = (y - cy) * z / focal_length
    
    return (x_3d, y_3d, z)

# ========== Pipeline (최적화) ==========
def create_pipeline():
    pipeline = dai.Pipeline()
    
    # ColorCamera - 해상도 축소
    cam_rgb = pipeline.create(dai.node.ColorCamera)
    cam_rgb.setPreviewSize(INPUT_SIZE[0], INPUT_SIZE[1])
    cam_rgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    cam_rgb.setInterleaved(False)
    cam_rgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    cam_rgb.setFps(30)
    
    # Neural Network
    nn = pipeline.create(dai.node.NeuralNetwork)
    nn.setBlobPath(BLOB_PATH)
    nn.setNumInferenceThreads(2)
    nn.input.setBlocking(False)
    
    cam_rgb.preview.link(nn.input)
    
    # MonoCamera - 해상도 낮춤
    mono_left = pipeline.create(dai.node.MonoCamera)
    mono_right = pipeline.create(dai.node.MonoCamera)
    mono_left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    mono_right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    mono_left.setBoardSocket(dai.CameraBoardSocket.LEFT)
    mono_right.setBoardSocket(dai.CameraBoardSocket.RIGHT)
    mono_left.setFps(20)  # FPS 낮춤
    mono_right.setFps(20)
    
    # StereoDepth - 설정 단순화
    stereo = pipeline.create(dai.node.StereoDepth)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
    stereo.setLeftRightCheck(False)  # 속도 향상
    stereo.setExtendedDisparity(False)
    stereo.setSubpixel(False)  # 속도 향상
    
    mono_left.out.link(stereo.left)
    mono_right.out.link(stereo.right)
    
    # XLinkOut
    xout_rgb = pipeline.create(dai.node.XLinkOut)
    xout_rgb.setStreamName("rgb")
    cam_rgb.preview.link(xout_rgb.input)
    
    xout_nn = pipeline.create(dai.node.XLinkOut)
    xout_nn.setStreamName("nn")
    nn.out.link(xout_nn.input)
    
    xout_depth = pipeline.create(dai.node.XLinkOut)
    xout_depth.setStreamName("depth")
    stereo.depth.link(xout_depth.input)
    
    return pipeline

# ========== 메인 ==========
def main():
    if not Path(BLOB_PATH).exists():
        print(f"Error: {BLOB_PATH} 파일이 없습니다.")
        return
    
    pipeline = create_pipeline()
    
    print("=" * 70)
    print("YOLOv8 + 3D 좌표 (고속 버전)")
    print("=" * 70)
    print(f"최적화 설정:")
    print(f"  - 화면 크기: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}")
    print(f"  - 처리 빈도: {PROCESS_EVERY_N_FRAMES}프레임마다 1번")
    print(f"  - Depth 업데이트: {DEPTH_EVERY_N_FRAMES}프레임마다 1번")
    print("=" * 70)
    
    with dai.Device(pipeline) as device:
        print("✓ OAK-D-Lite 연결!")
        print("✓ 고속 처리 시작 (종료: 'q')")
        print("=" * 70)
        
        q_rgb = device.getOutputQueue(name="rgb", maxSize=2, blocking=False)
        q_nn = device.getOutputQueue(name="nn", maxSize=2, blocking=False)
        q_depth = device.getOutputQueue(name="depth", maxSize=2, blocking=False)
        
        frame_count = 0
        detection_count = 0
        
        # 캐시된 결과 (프레임 스킵용)
        last_boxes = []
        last_confidences = []
        last_class_ids = []
        last_coords_3d = None
        last_depth_frame = None
        
        # FPS 측정
        fps_start_time = time.time()
        fps_frame_count = 0
        current_fps = 0
        
        while True:
            in_rgb = q_rgb.tryGet()
            in_nn = q_nn.tryGet()
            in_depth = q_depth.tryGet()
            
            if in_rgb is not None:
                frame_count += 1
                fps_frame_count += 1
                
                frame = in_rgb.getCvFrame()
                
                if frame is None or frame.size == 0:
                    continue
                
                # 화면 크기 조정 (빠른 표시)
                if frame.shape[:2] != (DISPLAY_HEIGHT, DISPLAY_WIDTH):
                    frame = cv2.resize(frame, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
                
                # FPS 계산 (1초마다)
                if time.time() - fps_start_time > 1.0:
                    current_fps = fps_frame_count / (time.time() - fps_start_time)
                    fps_start_time = time.time()
                    fps_frame_count = 0
                
                # NN 처리 (N프레임마다)
                if frame_count % PROCESS_EVERY_N_FRAMES == 0 and in_nn is not None:
                    try:
                        output_raw = np.array(in_nn.getFirstLayerFp16())
                        
                        total_elements = output_raw.size
                        if total_elements % 84 == 0:
                            num_predictions = total_elements // 84
                            output = output_raw.reshape(1, 84, num_predictions)
                        elif total_elements % 5 == 0:
                            num_predictions = total_elements // 5
                            output = output_raw.reshape(1, 5, num_predictions)
                        else:
                            output = output_raw.reshape(1, 5, -1)
                        
                        boxes, confidences, class_ids = decode_yolov8_raw(output, CONF_THRESHOLD)
                        
                        if len(boxes) > 0:
                            boxes_xyxy = xywh2xyxy_yolov8(
                                boxes, DISPLAY_WIDTH, DISPLAY_HEIGHT, INPUT_SIZE[0], INPUT_SIZE[1]
                            )
                            
                            keep_indices = nms_fast(boxes_xyxy, confidences, IOU_THRESHOLD)
                            
                            # 단일 객체
                            if len(keep_indices) > 1:
                                best_idx = keep_indices[np.argmax(confidences[keep_indices])]
                                keep_indices = [best_idx]
                            
                            # 캐시 업데이트
                            last_boxes = boxes_xyxy[keep_indices]
                            last_confidences = confidences[keep_indices]
                            last_class_ids = class_ids[keep_indices]
                            detection_count += len(keep_indices)
                        else:
                            last_boxes = []
                    
                    except Exception as e:
                        print(f"[오류] {e}")
                
                # Depth 업데이트 (더 적게)
                if frame_count % DEPTH_EVERY_N_FRAMES == 0 and in_depth is not None:
                    last_depth_frame = in_depth.getFrame()
                
                # 시각화 (캐시된 결과 사용)
                if len(last_boxes) > 0:
                    for idx in range(len(last_boxes)):
                        x1, y1, x2, y2 = last_boxes[idx].astype(int)
                        conf = last_confidences[idx]
                        class_id = last_class_ids[idx]
                        
                        x_center = (x1 + x2) // 2
                        y_center = (y1 + y2) // 2
                        
                        # 3D 좌표 (depth 프레임이 있을 때만)
                        coords_3d = None
                        if last_depth_frame is not None and frame_count % DEPTH_EVERY_N_FRAMES == 0:
                            coords_3d = get_3d_coordinates_fast(
                                last_depth_frame, x_center, y_center, frame.shape
                            )
                            if coords_3d:
                                last_coords_3d = coords_3d
                        
                        # 캐시된 3D 좌표 사용
                        if coords_3d is None and last_coords_3d is not None:
                            coords_3d = last_coords_3d
                        
                        # 시각화
                        color = (0, 255, 0)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                        
                        # 간단한 라벨
                        label = f"{CLASS_NAMES.get(class_id, 'Unknown')}: {conf:.2f}"
                        if coords_3d:
                            x_3d, y_3d, z_3d = coords_3d
                            label += f" | {z_3d/1000:.2f}m"
                        
                        # 라벨 배경
                        (label_w, label_h), _ = cv2.getTextSize(
                            label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
                        )
                        cv2.rectangle(frame, (x1, y1 - label_h - 10), (x1 + label_w + 5, y1), color, -1)
                        cv2.putText(frame, label, (x1 + 2, y1 - 5),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                        
                        # 중심점
                        cv2.circle(frame, (x_center, y_center), 5, (0, 0, 255), -1)
                        
                        # 콘솔 출력 (10프레임마다)
                        if coords_3d and frame_count % 10 == 0:
                            x_3d, y_3d, z_3d = coords_3d
                            print(f"[{frame_count:4d}] {CLASS_NAMES.get(class_id):8s} | "
                                  f"Conf: {conf:.2f} | Z={z_3d/1000:.2f}m ({z_3d/10:.0f}cm)")
                
                # FPS 표시
                info_text = f"FPS: {current_fps:.1f} | Frame: {frame_count} | Detected: {len(last_boxes)}"
                cv2.rectangle(frame, (5, 5), (400, 35), (0, 0, 0), -1)
                cv2.putText(frame, info_text, (10, 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                
                # 화면 표시
                cv2.imshow("YOLOv8 + 3D (Fast)", frame)
            
            if cv2.waitKey(1) == ord('q'):
                break
        
        print("\n" + "=" * 70)
        print(f"평균 FPS: {current_fps:.1f}")
        print(f"총 프레임: {frame_count} | 총 검출: {detection_count}")
        print("=" * 70)
    
    cv2.destroyAllWindows()
    print("종료")

if __name__ == "__main__":
    main()