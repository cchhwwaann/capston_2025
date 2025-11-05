import math

L1 = 15.0  # 붐(Boom) 길이 (J1 to J2)
L2 = 10.0  # 암(Arm) 길이 (J2 to J3)
L3 = 5.0   # 버킷(Bucket) 길이 (J3 to PE)

# J1 관절 (붐 시작점)의 좌표를 원점으로 가정
J1 = (0.0, 0.0, 0.0)

def inverse_kinematics_from_points(P3_coords, P4_coords):
    """
    P3 (암 끝단, J3)와 P4 (버킷 끝단, PE)의 공간 좌표를 사용하여S
    굴착기 관절 각도 (theta1, theta2, theta3)를 계산

    :param P3_coords: P3의 (x, y, z) 좌표 튜플
    :param P4_coords: P4의 (x, y, z) 좌표 튜플
    :return: (theta1, theta2, theta3) 라디안 각도 튜플, 해가 없으면 None 반환
    """
    x_P3, y_P3, z_P3 = P3_coords
    x_P4, y_P4, z_P4 = P4_coords
    
    # 굴착기는 XY 평면 내 움직임으로 단순화하여 Z 좌표는 무시하거나 높이 축으로 사용
    # 여기서는 Y축이 수직(높이)이고 X축이 수평면으로 간주하는 일반적인 로봇 팔 좌표계를 따릅니다.
    # 즉, 굴착기 기구학은 (X, Y) 평면에서 해석됩니다.

    # ----------------------------------------------------
    # 1. 2링크 IK 문제로 단순화: P3 좌표를 이용해 theta1, theta2 계산
    # ----------------------------------------------------
    
    # J1에서 P3까지의 수평 거리 R
    R_sq = x_P3**2 + y_P3**2  # Z축은 깊이 카메라 기준이므로, 여기서는 XY 평면상의 거리만 사용
    R = math.sqrt(R_sq)

    # 링크 길이 검증 (J1과 P3 사이 거리가 L1 + L2와 일치해야 함)
    # 실제로는 오차를 허용해야 하지만, 이상적인 경우 L1+L2 = R
    # 여기서는 2링크 IK 해법을 위해 P_L3 = P3로 간주합니다.
    
    # L1과 P3 사이 거리 R이 L1, L2로 만들 수 없는 거리인지 확인
    if R > L1 + L2 or R < abs(L1 - L2):
        print(f"오류: P3 지점 ({R:.2f})은 도달 불가능합니다 (L1+L2={L1+L2}).")
        return None
    
    # --- theta2 계산 (코사인 법칙) ---
    # cos(theta2_prime) = (L1^2 + L2^2 - R^2) / (2 * L1 * L2)
    cos_theta2_prime = (L1**2 + L2**2 - R_sq) / (2 * L1 * L2)
    cos_theta2_prime = max(-1.0, min(1.0, cos_theta2_prime)) 
    
    theta2_prime = math.acos(cos_theta2_prime)
    
    # 실제 관절 각도 theta2 (엘보우 다운 자세 가정)
    # 굴착기는 보통 theta2가 음수(Boom에 대해 아래로 꺾임)입니다.
    theta2 = -(math.pi - theta2_prime) 

    # --- theta1 계산 ---
    gamma = math.atan2(y_P3, x_P3) # J1에서 P3까지의 절대 각도
    
    # delta = acos((R^2 + L1^2 - L2^2) / (2 * R * L1))
    cos_delta = (R_sq + L1**2 - L2**2) / (2 * R * L1)
    cos_delta = max(-1.0, min(1.0, cos_delta)) 
    
    delta = math.acos(cos_delta)
    
    # theta1 계산 (붐의 절대 각도, 엘보우 다운 자세)
    theta1 = gamma - delta

    # ----------------------------------------------------
    # 2. 버킷 각도 theta3 계산
    # ----------------------------------------------------
    
    # A. P3와 P4 벡터 (버킷 벡터)의 절대각 (alpha_bucket) 계산
    
    # 버킷 벡터 (P3 -> P4)
    vx_bucket = x_P4 - x_P3
    vy_bucket = y_P4 - y_P3
    
    # P3 -> P4 벡터의 절대각 (수평면 대비)
    alpha_bucket = math.atan2(vy_bucket, vx_bucket) 
    
    # B. 암의 절대각 (theta_arm_absolute) 계산
    theta_arm_absolute = theta1 + theta2 # 암이 수평면에 대해 이루는 각도
    
    # C. theta3 = alpha_bucket - theta_arm_absolute
    # theta3는 암에 대한 버킷의 상대각
    theta3 = alpha_bucket - theta_arm_absolute
    
    return theta1, theta2, theta3

# --- 사용 예시 ---

# 3D 카메라로 측정된 두 지점의 좌표 (단위는 L1, L2, L3와 동일해야 함)
# P3: (15, 10) 지점, P4: (18, 5) 지점이라고 가정
P3_TARGET = (15.0, 10.0, 0.0) # (x, y, z)
P4_TARGET = (18.0, 5.0, 0.0) # (x, y, z)

result = inverse_kinematics_from_points(P3_TARGET, P4_TARGET)

if result:
    theta1_rad, theta2_rad, theta3_rad = result
    
    # 결과를 보기 쉽게 각도(Degree)로 변환
    theta1_deg = math.degrees(theta1_rad)
    theta2_deg = math.degrees(theta2_rad)
    theta3_deg = math.degrees(theta3_rad)

    print(f"\n--- 3D 좌표 기반 역기구학 계산 결과 ---")
    print(f"P3 (암 끝단) 좌표: {P3_TARGET}")
    print(f"P4 (버킷 끝단) 좌표: {P4_TARGET}")
    print("-" * 40)
    print(f"붐 관절 (θ1): {theta1_deg:.2f} deg ({theta1_rad:.3f} rad)")
    print(f"암 관절 (θ2): {theta2_deg:.2f} deg ({theta2_rad:.3f} rad)")
    print(f"버킷 관절 (θ3): {theta3_deg:.2f} deg ({theta3_rad:.3f} rad)")
    print("-" * 40)
else:
    print("계산에 실패했습니다. 입력 좌표를 확인하십시오.")