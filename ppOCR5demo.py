"""
Minimal demo that sends a local image through the olmOCR pipeline.

Export OLMOCR_SERVER_URL / OLMOCR_MODEL / OLMOCR_API_KEY before running this script,
or edit the OCRProcessor constructor to point to your deployment.
"""

from pathlib import Path

import numpy as np
from PIL import Image

from ocr_module import OCRProcessor


def main(image_path: str = "02.png") -> None:
    ocr = OCRProcessor()
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"{path} was not found")

    image = Image.open(path).convert("RGB")
    results = ocr.process_image(np.array(image))

    if not results:
        print("No text extracted.")
        return

    print(f"olmOCR extracted {len(results)} lines from {path}:")
    for text, _ in results:
        print(text)


if __name__ == "__main__":
    main()
