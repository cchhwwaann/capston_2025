import depthai as dai
import cv2
import numpy as np

# ========== 설정 ==========
DISPLAY_WIDTH = 640
DISPLAY_HEIGHT = 480

# ========== 3D 좌표 계산 ==========
def get_3d_coordinates(depth_frame, x_pixel, y_pixel, calibration_data=None):
    """
    특정 픽셀 위치의 3D 좌표 계산
    
    Args:
        depth_frame: depth map (numpy array)
        x_pixel, y_pixel: RGB 이미지 상의 픽셀 좌표
        calibration_data: 카메라 캘리브레이션 데이터 (옵션)
    
    Returns:
        (x_3d, y_3d, z_3d): 3D 좌표 (mm 단위) 또는 None
    """
    depth_h, depth_w = depth_frame.shape[:2]
    
    # 좌표 범위 체크
    x = int(np.clip(x_pixel, 0, depth_w - 1))
    y = int(np.clip(y_pixel, 0, depth_h - 1))
    
    # 주변 영역 평균으로 노이즈 감소 (5x5 윈도우)
    window_size = 5
    x_start = max(0, x - window_size // 2)
    x_end = min(depth_w, x + window_size // 2 + 1)
    y_start = max(0, y - window_size // 2)
    y_end = min(depth_h, y + window_size // 2 + 1)
    
    depth_window = depth_frame[y_start:y_end, x_start:x_end]
    valid_depths = depth_window[depth_window > 0]
    
    if len(valid_depths) == 0:
        return None
    
    # 중앙값으로 depth 추출 (이상치에 강함)
    depth_mm = np.median(valid_depths)
    
    # OAK-D-Lite 기본 파라미터 (실제 캘리브레이션 값 사용 가능)
    if calibration_data:
        focal_length = calibration_data['focal_length']
        cx = calibration_data['cx']
        cy = calibration_data['cy']
    else:
        # 기본값 (OAK-D-Lite 근사값)
        focal_length = 440  # 픽셀 단위
        cx = depth_w / 2
        cy = depth_h / 2
    
    # 3D 좌표 계산
    z = depth_mm
    x_3d = (x - cx) * z / focal_length
    y_3d = (y - cy) * z / focal_length
    
    return (x_3d, y_3d, z)

def create_pipeline():
    """depth와 RGB를 위한 파이프라인 생성"""
    pipeline = dai.Pipeline()
    
    # RGB Camera
    cam_rgb = pipeline.create(dai.node.ColorCamera)
    cam_rgb.setPreviewSize(DISPLAY_WIDTH, DISPLAY_HEIGHT)
    cam_rgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    cam_rgb.setInterleaved(False)
    cam_rgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    cam_rgb.setFps(30)
    
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
    
    xout_depth = pipeline.create(dai.node.XLinkOut)
    xout_depth.setStreamName("depth")
    stereo.depth.link(xout_depth.input)
    
    return pipeline

def mouse_callback(event, x, y, flags, param):
    """마우스 클릭 시 해당 위치의 3D 좌표 측정"""
    if event == cv2.EVENT_LBUTTONDOWN:
        depth_frame = param['depth_frame']
        
        if depth_frame is not None:
            # RGB 이미지와 depth 이미지 크기가 다를 수 있으므로 스케일링
            depth_h, depth_w = depth_frame.shape[:2]
            rgb_h, rgb_w = param['rgb_frame'].shape[:2] if param['rgb_frame'] is not None else (DISPLAY_HEIGHT, DISPLAY_WIDTH)
            
            x_depth = int(x * depth_w / rgb_w)
            y_depth = int(y * depth_h / rgb_h)
            
            coords_3d = get_3d_coordinates(depth_frame, x_depth, y_depth)
            
            if coords_3d:
                x_3d, y_3d, z_3d = coords_3d
                print(f"\n[클릭 위치] 픽셀: ({x}, {y})")
                print(f"[3D 좌표] X: {x_3d/1000:.3f}m, Y: {y_3d/1000:.3f}m, Z: {z_3d/1000:.3f}m")
                print(f"[거리] {z_3d/1000:.3f}m = {z_3d/10:.1f}cm")
            else:
                print(f"\n[클릭 위치] 픽셀: ({x}, {y}) - Depth 데이터 없음")

def main():
    pipeline = create_pipeline()
    
    print("=" * 70)
    print("OAK-D-Lite 3D 좌표 측정 프로그램")
    print("=" * 70)
    print("사용법:")
    print("  - 화면을 클릭하면 해당 위치의 3D 좌표가 출력됩니다")
    print("  - 'q' 키를 누르면 종료됩니다")
    print("=" * 70)
    
    with dai.Device(pipeline) as device:
        print("✓ OAK-D-Lite 연결 완료!\n")
        
        q_rgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
        q_depth = device.getOutputQueue(name="depth", maxSize=4, blocking=False)
        
        # 마우스 콜백을 위한 공유 데이터
        shared_data = {
            'depth_frame': None,
            'rgb_frame': None
        }
        
        cv2.namedWindow("3D Coordinate Measurement")
        cv2.setMouseCallback("3D Coordinate Measurement", mouse_callback, shared_data)
        
        frame_count = 0
        
        while True:
            in_rgb = q_rgb.tryGet()
            in_depth = q_depth.tryGet()
            
            if in_rgb is not None:
                frame = in_rgb.getCvFrame()
                shared_data['rgb_frame'] = frame
                
                if in_depth is not None:
                    depth_frame = in_depth.getFrame()
                    shared_data['depth_frame'] = depth_frame
                    
                    # Depth map 시각화
                    depth_colormap = cv2.applyColorMap(
                        cv2.convertScaleAbs(depth_frame, alpha=255/10000),
                        cv2.COLORMAP_JET
                    )
                    
                    # 화면 중앙의 3D 좌표 표시
                    center_x = frame.shape[1] // 2
                    center_y = frame.shape[0] // 2
                    
                    depth_h, depth_w = depth_frame.shape[:2]
                    x_depth = int(center_x * depth_w / frame.shape[1])
                    y_depth = int(center_y * depth_h / frame.shape[0])
                    
                    coords_3d = get_3d_coordinates(depth_frame, x_depth, y_depth)
                    
                    # 십자선 그리기
                    cv2.line(frame, (center_x - 20, center_y), (center_x + 20, center_y), (0, 255, 0), 2)
                    cv2.line(frame, (center_x, center_y - 20), (center_x, center_y + 20), (0, 255, 0), 2)
                    cv2.circle(frame, (center_x, center_y), 5, (0, 0, 255), -1)
                    
                    # 중앙 좌표 정보 표시
                    if coords_3d:
                        x_3d, y_3d, z_3d = coords_3d
                        info_text = f"Center: X={x_3d/1000:.2f}m, Y={y_3d/1000:.2f}m, Z={z_3d/1000:.2f}m"
                        
                        # 배경
                        cv2.rectangle(frame, (5, 5), (590, 70), (0, 0, 0), -1)
                        
                        # 텍스트
                        cv2.putText(frame, "Click anywhere to measure 3D coordinates",
                                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                        cv2.putText(frame, info_text,
                                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    
                    # Frame 정보
                    frame_count += 1
                    cv2.putText(frame, f"Frame: {frame_count}",
                                (frame.shape[1] - 150, 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    # 화면 표시
                    cv2.imshow("3D Coordinate Measurement", frame)
                    cv2.imshow("Depth Map", depth_colormap)
            
            if cv2.waitKey(1) == ord('q'):
                break
    
    cv2.destroyAllWindows()
    print("\n프로그램 종료")

if __name__ == "__main__":
    main()