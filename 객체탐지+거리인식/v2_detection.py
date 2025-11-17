import depthai as dai
import cv2
import numpy as np
from pathlib import Path

# ========== 설정 ==========
BLOB_PATH = "runs/detect/train/weights/best_openvino_model/best.blob"
CLASS_NAMES = {0: "bucket"}
INPUT_SIZE = (416, 416)
CONF_THRESHOLD = 0.25  # 신뢰도 임계값 (0~1 범위)
IOU_THRESHOLD = 0.45   # NMS IOU 임계값

# ========== YOLOv8 후처리 함수 (NMS=false 버전) ==========
def decode_yolov8_raw(output, conf_threshold=0.25, input_shape=(416, 416)):
    """
    YOLOv8 raw 출력 디코딩 (NMS=false일 때)
    output shape: (1, 84, num_predictions) 
    - 84 = 4(bbox) + 80(classes) for COCO, 또는 4 + num_classes
    """
    # 출력 형식 확인
    if len(output.shape) == 3:
        predictions = output[0].T  # (num_predictions, 84)
    elif len(output.shape) == 2:
        predictions = output.T
    else:
        predictions = output
    
    # predictions shape: (num_predictions, 4 + num_classes)
    boxes = predictions[:, :4]  # x_center, y_center, width, height (normalized 0~input_size)
    
    # 클래스 점수 추출
    if predictions.shape[1] > 5:
        # 다중 클래스
        class_scores = predictions[:, 4:]
        class_ids = np.argmax(class_scores, axis=1)
        confidences = np.max(class_scores, axis=1)
    else:
        # 단일 클래스 (objectness만)
        confidences = predictions[:, 4]
        class_ids = np.zeros(len(confidences), dtype=int)
    
    # 신뢰도 필터링
    mask = confidences > conf_threshold
    boxes = boxes[mask]
    confidences = confidences[mask]
    class_ids = class_ids[mask]
    
    return boxes, confidences, class_ids

def xywh2xyxy_yolov8(boxes, img_width, img_height, input_width=416, input_height=416):
    """
    YOLOv8 좌표 변환: 중심점(xywh) -> 코너(xyxy)
    boxes: (N, 4) - x_center, y_center, width, height (0~416 범위)
    """
    if len(boxes) == 0:
        return np.array([])
    
    # YOLOv8 출력은 input_size 기준 좌표
    scale_x = img_width / input_width
    scale_y = img_height / input_height
    
    x_center = boxes[:, 0] * scale_x
    y_center = boxes[:, 1] * scale_y
    width = boxes[:, 2] * scale_x
    height = boxes[:, 3] * scale_y
    
    x1 = x_center - width / 2
    y1 = y_center - height / 2
    x2 = x_center + width / 2
    y2 = y_center + height / 2
    
    # 좌표를 이미지 범위 내로 클리핑
    x1 = np.clip(x1, 0, img_width)
    y1 = np.clip(y1, 0, img_height)
    x2 = np.clip(x2, 0, img_width)
    y2 = np.clip(y2, 0, img_height)
    
    return np.stack([x1, y1, x2, y2], axis=1)

def nms(boxes, scores, iou_threshold=0.45):
    """Non-Maximum Suppression"""
    if len(boxes) == 0:
        return []
    
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    
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

# ========== Pipeline 설정 ==========
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
    
    # XLinkOut
    xout_rgb = pipeline.create(dai.node.XLinkOut)
    xout_rgb.setStreamName("rgb")
    cam_rgb.preview.link(xout_rgb.input)
    
    xout_nn = pipeline.create(dai.node.XLinkOut)
    xout_nn.setStreamName("nn")
    nn.out.link(xout_nn.input)
    
    return pipeline

# ========== 메인 루프 ==========
def main():
    if not Path(BLOB_PATH).exists():
        print(f"Error: blob 파일을 찾을 수 없습니다: {BLOB_PATH}")
        return
    
    pipeline = create_pipeline()
    
    print("=" * 70)
    print("YOLOv8 객체 탐지 (단일 객체 모드)")
    print("=" * 70)
    
    with dai.Device(pipeline) as device:
        print("✓ OAK-D-Lite 연결 완료!")
        
        q_rgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
        q_nn = device.getOutputQueue(name="nn", maxSize=4, blocking=False)
        
        print("✓ 실시간 탐지 시작 (종료: 'q' 키)")
        print("=" * 70)
        
        frame_count = 0
        detection_count = 0
        
        # 디버깅 플래그
        debug_output_once = True
        
        while True:
            in_rgb = q_rgb.tryGet()
            in_nn = q_nn.tryGet()
            
            if in_rgb is not None and in_nn is not None:
                frame_count += 1
                
                # RGB 프레임
                frame = in_rgb.getCvFrame()
                
                if frame is None or frame.size == 0:
                    continue
                
                # NN 출력 처리
                try:
                    output_raw = np.array(in_nn.getFirstLayerFp16())
                    
                    # 첫 프레임에서 출력 형식 디버깅
                    if debug_output_once:
                        print(f"\n[디버그] NN 출력 정보:")
                        print(f"  - Raw shape: {output_raw.shape}")
                        print(f"  - Raw size: {output_raw.size}")
                        print(f"  - Value range: [{output_raw.min():.2f}, {output_raw.max():.2f}]")
                        
                        # 가능한 reshape 시도
                        possible_shapes = [
                            (1, 84, -1),
                            (1, 5, -1),
                            (84, -1),
                            (5, -1),
                            (-1, 84),
                            (-1, 5)
                        ]
                        
                        for shape in possible_shapes:
                            try:
                                test_output = output_raw.reshape(shape)
                                print(f"  - Possible shape: {test_output.shape}")
                            except:
                                pass
                        
                        debug_output_once = False
                        print()
                    
                    # 출력 형식 자동 감지
                    total_elements = output_raw.size
                    
                    # 가능한 예측 개수 계산
                    if total_elements % 84 == 0:
                        num_predictions = total_elements // 84
                        output = output_raw.reshape(1, 84, num_predictions)
                    elif total_elements % 5 == 0:
                        num_predictions = total_elements // 5
                        output = output_raw.reshape(1, 5, num_predictions)
                    else:
                        # fallback: 가장 가까운 형식 추정
                        num_predictions = int(np.sqrt(total_elements / 5))
                        output = output_raw.reshape(1, 5, -1)
                    
                    # 디코딩
                    boxes, confidences, class_ids = decode_yolov8_raw(
                        output, 
                        conf_threshold=CONF_THRESHOLD,
                        input_shape=INPUT_SIZE
                    )
                    
                    # 검출 결과가 있을 때만 처리
                    if len(boxes) > 0:
                        # 좌표 변환
                        boxes_xyxy = xywh2xyxy_yolov8(
                            boxes, 
                            frame.shape[1], 
                            frame.shape[0],
                            INPUT_SIZE[0],
                            INPUT_SIZE[1]
                        )
                        
                        # NMS 적용
                        keep_indices = nms(boxes_xyxy, confidences, IOU_THRESHOLD)
                        
                        # 단일 객체 모드: 가장 높은 신뢰도만 유지
                        if len(keep_indices) > 1:
                            best_idx = keep_indices[np.argmax(confidences[keep_indices])]
                            keep_indices = [best_idx]
                        
                        detection_count += len(keep_indices)
                        
                        # 결과 그리기
                        for idx in keep_indices:
                            x1, y1, x2, y2 = boxes_xyxy[idx].astype(int)
                            conf = confidences[idx]
                            class_id = class_ids[idx]
                            
                            # Bounding box 중심점
                            x_center = (x1 + x2) // 2
                            y_center = (y1 + y2) // 2
                            
                            # 시각화
                            color = (0, 255, 0)
                            thickness = 3
                            
                            # Bounding box
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
                            
                            # 라벨
                            label = f"{CLASS_NAMES.get(class_id, 'Unknown')}: {conf:.2f}"
                            
                            # 라벨 배경
                            (label_w, label_h), baseline = cv2.getTextSize(
                                label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
                            )
                            
                            cv2.rectangle(
                                frame, 
                                (x1, y1 - label_h - 15), 
                                (x1 + label_w + 10, y1), 
                                color, 
                                -1
                            )
                            
                            cv2.putText(
                                frame, 
                                label, 
                                (x1 + 5, y1 - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 
                                0.7, 
                                (0, 0, 0), 
                                2
                            )
                            
                            # 중심점 표시
                            cv2.circle(frame, (x_center, y_center), 8, (0, 0, 255), -1)
                            cv2.circle(frame, (x_center, y_center), 4, (255, 255, 255), -1)
                            
                            # 콘솔 출력 (5프레임마다)
                            if frame_count % 5 == 0:
                                bbox_area = (x2 - x1) * (y2 - y1)
                                print(f"[Frame {frame_count:4d}] {CLASS_NAMES.get(class_id, 'Unknown'):8s} | "
                                      f"Conf: {conf:.3f} | "
                                      f"Box: ({x1:3d},{y1:3d})-({x2:3d},{y2:3d}) | "
                                      f"Area: {bbox_area:5d}px²")
                    
                    # FPS 및 통계 정보
                    info_text = f"Frame: {frame_count} | Objects Detected: {len(keep_indices) if len(boxes) > 0 else 0}"
                    cv2.rectangle(frame, (5, 5), (550, 45), (0, 0, 0), -1)
                    cv2.putText(
                        frame, 
                        info_text, 
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        0.7, 
                        (255, 255, 255), 
                        2
                    )
                    
                except Exception as e:
                    print(f"[오류] NN 출력 처리 실패: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
                
                # 화면 표시
                cv2.imshow("YOLOv8 Object Detection", frame)
            
            if cv2.waitKey(1) == ord('q'):
                break
        
        print("\n" + "=" * 70)
        print(f"총 처리 프레임: {frame_count}")
        print(f"총 검출 횟수: {detection_count}")
        print("=" * 70)
    
    cv2.destroyAllWindows()
    print("프로그램 종료")

if __name__ == "__main__":
    main()