import matplotlib.pyplot as plt
import numpy as np

# 시간 (0~100% 주기로 표현)
t = np.linspace(0, 1, 500)
y = np.zeros_like(t)

# 단계 비율 설정
t1, t2, t3, t4 = 0.25, 0.6, 0.8, 1.0  # 굴착, 이송, 투하, 복귀 비율

# 버킷 흙 양 정의
for i, ti in enumerate(t):
    if ti < t1:  # 굴착 (증가)
        y[i] = (ti / t1)
    elif ti < t2:  # 이송 (유지)
        y[i] = 1
    elif ti < t3:  # 투하 (감소)
        y[i] = 1 - (ti - t2) / (t3 - t2)
    else:  # 복귀 (0 유지)
        y[i] = 0

# 그래프 출력
plt.figure(figsize=(8,4))
plt.plot(t, y, linewidth=3)
plt.title("Excavator Cycle Time vs Bucket Fill Amount")
plt.xlabel("Cycle Time (normalized)")
plt.ylabel("Bucket Fill Amount (relative)")
plt.grid(True)
plt.show()
