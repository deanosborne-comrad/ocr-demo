import argparse
import io
import json
import logging
import os
from pathlib import Path
from typing import Iterable, List

import cairosvg
import numpy as np
import psycopg2
from dotenv import load_dotenv
from pdf2image import convert_from_bytes
from PIL import Image

from ocr_module import OCRProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocr-runner")


def load_image(path: Path) -> np.ndarray:
    image = Image.open(path).convert("RGB")
    return np.array(image)


def run_single_image(ocr: OCRProcessor, path: Path) -> dict:
    image_np = load_image(path)
    lines = run_ocr_on_array(ocr, image_np)
    return {
        "source": "file",
        "file": str(path),
        "pages": [{"page": 1, "lines": lines}],
        "success": True,
    }


def run_ocr_on_array(ocr: OCRProcessor, image_np: np.ndarray) -> List[dict]:
    results = ocr.process_image(image_np)
    return [{"text": text, "score": score} for text, score in results]


def connect_db():
    required = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASS")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(f"Missing DB environment variables: {', '.join(missing)}")
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
    )


def fetch_blob(conn, blob_id: int):
    with conn.cursor() as cur:
        cur.execute("SELECT cb_file_path, cb_binary FROM case_blob WHERE cb_serial = %s", (blob_id,))
        row = cur.fetchone()
        if not row:
            return None, None
        return row[0], row[1]


def binary_to_images(binary: bytes, filename: str) -> Iterable[np.ndarray]:
    suffix = (Path(filename).suffix or "").lower()

    if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
        image = Image.open(io.BytesIO(binary)).convert("RGB")
        yield np.array(image)
        return

    if suffix == ".pdf":
        pages = convert_from_bytes(binary, dpi=300)
        for page in pages:
            yield np.array(page.convert("RGB"))
        return

    if suffix == ".svg":
        png_bytes = cairosvg.svg2png(bytestring=binary)
        image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        yield np.array(image)
        return

    # Fallback: try to interpret as image
    image = Image.open(io.BytesIO(binary)).convert("RGB")
    yield np.array(image)


def run_blob(ocr: OCRProcessor, conn, blob_id: int) -> dict:
    filename, binary = fetch_blob(conn, blob_id)
    if not binary:
        return {"source": "blob", "blob_id": blob_id, "success": False, "error": "not_found"}

    pages = []
    for idx, image_np in enumerate(binary_to_images(binary, filename or f"blob_{blob_id}"), start=1):
        lines = run_ocr_on_array(ocr, image_np)
        pages.append({"page": idx, "lines": lines})

    return {
        "source": "blob",
        "blob_id": blob_id,
        "filename": filename,
        "pages": pages,
        "success": True,
    }


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run olmOCR on local files or Postgres blobs.")
    parser.add_argument("inputs", nargs="*", help="Image paths (PNG/JPG/PDF/SVG) to process.")
    parser.add_argument("--blob-ids", nargs="*", type=int, help="case_blob IDs to process via Postgres.")
    args = parser.parse_args()

    if not args.inputs and not args.blob_ids:
        parser.error("Provide at least one file path or --blob-ids.")

    ocr = OCRProcessor()
    conn = None
    payload = []

    for item in args.inputs:
        path = Path(item)
        if not path.exists():
            logger.error("File not found: %s", path)
            payload.append({"source": "file", "file": str(path), "success": False, "error": "file_not_found"})
            continue
        try:
            payload.append(run_single_image(ocr, path))
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.exception("Failed to process %s", path)
            payload.append({"source": "file", "file": str(path), "success": False, "error": str(exc)})

    if args.blob_ids:
        try:
            conn = connect_db()
        except Exception as exc:
            logger.exception("Failed to connect to Postgres")
            for blob_id in args.blob_ids:
                payload.append({"source": "blob", "blob_id": blob_id, "success": False, "error": f"db_error: {exc}"})
        else:
            with conn:
                for blob_id in args.blob_ids:
                    try:
                        payload.append(run_blob(ocr, conn, blob_id))
                    except Exception as exc:
                        logger.exception("Failed to process blob %s", blob_id)
                        payload.append({"source": "blob", "blob_id": blob_id, "success": False, "error": str(exc)})
        finally:
            if conn:
                conn.close()

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
