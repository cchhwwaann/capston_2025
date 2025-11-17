# split_train_val.py
from pathlib import Path
import random
import shutil

# ==== 설정 ====
BASE_DIR = Path(__file__).resolve().parent    # 현재 파일 기준 폴더 (1113)

# ⚠️ 폴더 이름 여기!
IMG_DIR = BASE_DIR / "rareimage"              # 원본 이미지 폴더
LABEL_DIR = BASE_DIR / "rarelabel"            # 원본 라벨(.txt) 폴더

OUT_IMG_DIR = BASE_DIR / "images"             # 새로 만들 images/train, images/val
OUT_LABEL_DIR = BASE_DIR / "labels"           # 새로 만들 labels/train, labels/val

train_ratio = 0.8                             # train 80%, val 20%
random.seed(42)                               # 섞기 고정

print("📁 BASE_DIR  :", BASE_DIR)
print("📁 IMG_DIR   :", IMG_DIR)
print("📁 LABEL_DIR :", LABEL_DIR)

# ==== 이미지 & 라벨 파일 수집 ====
img_files = []
for ext in ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]:
    img_files.extend(IMG_DIR.glob(ext))

print(f"찾은 이미지 개수: {len(img_files)}")

pairs = []
no_label = []

for img in img_files:
    # 이미지 이름이 0001.jpg면 라벨은 0001.txt로 가정
    label = LABEL_DIR / f"{img.stem}.txt"
    if label.exists():
        pairs.append((img, label))
    else:
        no_label.append(img.name)

print(f"✅ 매칭된 이미지-라벨 페어 수: {len(pairs)}")
print(f"⚠ 라벨 없는 이미지 수: {len(no_label)}")

if no_label:
    print("  예시(라벨 없는 이미지):", no_label[:10])

if not pairs:
    raise SystemExit("❌ 이미지-라벨 페어를 하나도 못 찾았어요. 파일 이름이 서로 같은지 확인해줘!")

# 섞기
random.shuffle(pairs)

# train / val 나누기
split_idx = int(len(pairs) * train_ratio)
train_pairs = pairs[:split_idx]
val_pairs = pairs[split_idx:]

print(f"→ train: {len(train_pairs)}개, val: {len(val_pairs)}개")

# ==== 폴더 생성 함수 ====
def prepare_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

prepare_dir(OUT_IMG_DIR / "train")
prepare_dir(OUT_IMG_DIR / "val")
prepare_dir(OUT_LABEL_DIR / "train")
prepare_dir(OUT_LABEL_DIR / "val")

# ==== 복사 함수 ====
def copy_pair(img_path: Path, label_path: Path, subset: str):
    dst_img = OUT_IMG_DIR / subset / img_path.name
    dst_label = OUT_LABEL_DIR / subset / label_path.name
    shutil.copy2(img_path, dst_img)
    shutil.copy2(label_path, dst_label)

# ==== 실제 복사 ====
for img, lbl in train_pairs:
    copy_pair(img, lbl, "train")

for img, lbl in val_pairs:
    copy_pair(img, lbl, "val")

print("✅ 이미지/라벨 train·val 분할 완료!")
print(f" - {OUT_IMG_DIR}")
print(f" - {OUT_LABEL_DIR}")
