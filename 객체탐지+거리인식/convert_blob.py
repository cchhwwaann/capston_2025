import blobconverter

blob_path = blobconverter.from_onnx(
    model="runs/detect/train/weights/best.onnx",
    data_type="FP16",
    shaves=6,
    version="2021.4",
    use_cache=False
)

print(f"Blob 파일 생성됨: {blob_path}")