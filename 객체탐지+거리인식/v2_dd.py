import depthai as dai
import cv2
import numpy as np
from pathlib import Path

# ========== 설정 ==========
BLOB_PATH = "runs/detect/train/weights/best_openvino_model/best.blob"
CLASS_NAMES = {0: "bucket"}
INPUT_SIZE = (416, 416)
CONF_THRESHOLD = 0.25
IOU_THRESHOLD = 0.45

# ========== YOLOv8 후처리 ==========
def decode_yolov8_raw(output, conf_threshold=0.25):
    """YOLOv8 raw 출력 디코딩"""
    if len(output.shape) == 3:
        predictions = output[0].T
    elif len(output.shape) == 2:
        predictions = output.T
    else:
        predictions = output
    
    boxes = predictions[:, :4]
    
    if predictions.shape[1] > 5:
        class_scores = predictions[:, 4:]
        class_ids = np.argmax(class_scores, axis=1)
        confidences = np.max(class_scores, axis=1)
    else:
        confidences = predictions[:, 4]
        class_ids = np.zeros(len(confidences), dtype=int)
    
    mask = confidences > conf_threshold
    return boxes[mask], confidences[mask], class_ids[mask]

def xywh2xyxy_yolov8(boxes, img_width, img_height, input_width=416, input_height=416):
    """YOLOv8 좌표 변환"""
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

def nms(boxes, scores, iou_threshold=0.45):
    """Non-Maximum Suppression"""
    if len(boxes) == 0:
        return []
    
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        
        if order.size == 1:
            break
        
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]
    
    return keep

# ========== 3D 좌표 계산 ==========
def get_3d_coordinates(depth_frame, x_pixel, y_pixel, rgb_shape):
    """
    특정 픽셀의 3D 좌표 계산
    
    Args:
        depth_frame: depth map
        x_pixel, y_pixel: RGB 이미지 상의 좌표
        rgb_shape: RGB 이미지 shape (height, width)
    
    Returns:
        (x_3d, y_3d, z_3d) in mm or None
    """
    depth_h, depth_w = depth_frame.shape[:2]
    rgb_h, rgb_w = rgb_shape[:2]
    
    # RGB 좌표를 Depth 좌표로 변환
    x_depth = int(x_pixel * depth_w / rgb_w)
    y_depth = int(y_pixel * depth_h / rgb_h)
    
    # 좌표 범위 제한
    x = int(np.clip(x_depth, 0, depth_w - 1))
    y = int(np.clip(y_depth, 0, depth_h - 1))
    
    # 5x5 윈도우의 중앙값으로 노이즈 감소
    window_size = 5
    x_start = max(0, x - window_size // 2)
    x_end = min(depth_w, x + window_size // 2 + 1)
    y_start = max(0, y - window_size // 2)
    y_end = min(depth_h, y + window_size // 2 + 1)
    
    depth_window = depth_frame[y_start:y_end, x_start:x_end]
    valid_depths = depth_window[depth_window > 0]
    
    if len(valid_depths) == 0:
        return None
    
    depth_mm = np.median(valid_depths)
    
    # OAK-D-Lite 카메라 파라미터
    focal_length = 440
    cx = depth_w / 2
    cy = depth_h / 2
    
    # 3D 좌표 계산 (mm)
    z = depth_mm
    x_3d = (x - cx) * z / focal_length
    y_3d = (y - cy) * z / focal_length
    
    return (x_3d, y_3d, z)

# ========== Pipeline ==========
def create_pipeline():
    pipeline = dai.Pipeline()
    
    # ColorCamera
    cam_rgb = pipeline.create(dai.node.ColorCamera)
    cam_rgb.setPreviewSize(416, 416)
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
    
    # MonoCamera (Left & Right)
    mono_left = pipeline.create(dai.node.MonoCamera)
    mono_right = pipeline.create(dai.node.MonoCamera)
    mono_left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    mono_right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    mono_left.setBoardSocket(dai.CameraBoardSocket.LEFT)
    mono_right.setBoardSocket(dai.CameraBoardSocket.RIGHT)
    
    # StereoDepth
    stereo = pipeline.create(dai.node.StereoDepth)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
    stereo.setLeftRightCheck(True)
    stereo.setExtendedDisparity(False)
    stereo.setSubpixel(True)
    
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
    print("YOLOv8 객체 탐지 + 3D 좌표 측정")
    print("=" * 70)
    
    with dai.Device(pipeline) as device:
        print("✓ OAK-D-Lite 연결!")
        print("✓ 실시간 처리 시작 (종료: 'q')")
        print("=" * 70)
        
        q_rgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
        q_nn = device.getOutputQueue(name="nn", maxSize=4, blocking=False)
        q_depth = device.getOutputQueue(name="depth", maxSize=4, blocking=False)
        
        frame_count = 0
        detection_count = 0
        
        while True:
            in_rgb = q_rgb.tryGet()
            in_nn = q_nn.tryGet()
            in_depth = q_depth.tryGet()
            
            if in_rgb is not None and in_nn is not None and in_depth is not None:
                frame_count += 1
                
                frame = in_rgb.getCvFrame()
                depth_frame = in_depth.getFrame()
                
                if frame is None or frame.size == 0:
                    continue
                
                try:
                    output_raw = np.array(in_nn.getFirstLayerFp16())
                    
                    # 자동 reshape
                    total_elements = output_raw.size
                    if total_elements % 84 == 0:
                        num_predictions = total_elements // 84
                        output = output_raw.reshape(1, 84, num_predictions)
                    elif total_elements % 5 == 0:
                        num_predictions = total_elements // 5
                        output = output_raw.reshape(1, 5, num_predictions)
                    else:
                        output = output_raw.reshape(1, 5, -1)
                    
                    # 디코딩
                    boxes, confidences, class_ids = decode_yolov8_raw(output, CONF_THRESHOLD)
                    
                    # 검출 처리
                    if len(boxes) > 0:
                        boxes_xyxy = xywh2xyxy_yolov8(
                            boxes, frame.shape[1], frame.shape[0], INPUT_SIZE[0], INPUT_SIZE[1]
                        )
                        
                        keep_indices = nms(boxes_xyxy, confidences, IOU_THRESHOLD)
                        
                        # 단일 객체: 최고 신뢰도만
                        if len(keep_indices) > 1:
                            best_idx = keep_indices[np.argmax(confidences[keep_indices])]
                            keep_indices = [best_idx]
                        
                        detection_count += len(keep_indices)
                        
                        for idx in keep_indices:
                            x1, y1, x2, y2 = boxes_xyxy[idx].astype(int)
                            conf = confidences[idx]
                            class_id = class_ids[idx]
                            
                            # 중심점
                            x_center = (x1 + x2) // 2
                            y_center = (y1 + y2) // 2
                            
                            # 3D 좌표
                            coords_3d = get_3d_coordinates(depth_frame, x_center, y_center, frame.shape)
                            
                            # 시각화
                            color = (0, 255, 0)
                            thickness = 3
                            
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
                            
                            # 라벨
                            label = f"{CLASS_NAMES.get(class_id, 'Unknown')}: {conf:.2f}"
                            if coords_3d:
                                x_3d, y_3d, z_3d = coords_3d
                                label += f" | {z_3d/1000:.2f}m"
                            
                            (label_w, label_h), _ = cv2.getTextSize(
                                label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
                            )
                            
                            cv2.rectangle(frame, (x1, y1 - label_h - 15), (x1 + label_w + 10, y1), color, -1)
                            cv2.putText(frame, label, (x1 + 5, y1 - 8),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
                            
                            # 중심점
                            cv2.circle(frame, (x_center, y_center), 8, (0, 0, 255), -1)
                            cv2.circle(frame, (x_center, y_center), 4, (255, 255, 255), -1)
                            
                            # 콘솔 출력
                            if coords_3d:
                                x_3d, y_3d, z_3d = coords_3d
                                print(f"[Frame {frame_count:4d}] {CLASS_NAMES.get(class_id):8s} | "
                                      f"Conf: {conf:.2f} | "
                                      f"3D: X={x_3d/1000:+.2f}m, Y={y_3d/1000:+.2f}m, Z={z_3d/1000:.2f}m | "
                                      f"Distance: {z_3d/10:.1f}cm")
                    
                    # 정보 표시
                    info_text = f"Frame: {frame_count} | Detected: {len(keep_indices) if len(boxes) > 0 else 0}"
                    cv2.rectangle(frame, (5, 5), (450, 45), (0, 0, 0), -1)
                    cv2.putText(frame, info_text, (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    
                except Exception as e:
                    print(f"[오류] {e}")
                    continue
                
                # Depth 시각화
                depth_colormap = cv2.applyColorMap(
                    cv2.convertScaleAbs(depth_frame, alpha=255/10000),
                    cv2.COLORMAP_JET
                )
                
                cv2.imshow("YOLOv8 + 3D Coordinates", frame)
                cv2.imshow("Depth Map", depth_colormap)
            
            if cv2.waitKey(1) == ord('q'):
                break
        
        print("\n" + "=" * 70)
        print(f"총 프레임: {frame_count} | 총 검출: {detection_count}")
        print("=" * 70)
    
    cv2.destroyAllWindows()
    print("종료")

if __name__ == "__main__":
    main()