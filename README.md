# Local olmOCR Pipeline (Quantized)

This repo turns your RTX 4050 laptop into a self-contained OCR workstation using **olmOCR**, AllenAI’s multimodal OCR model. There is **no downstream LLM** – once the image is processed the raw Markdown/plain text is returned directly from the model.

## Highlights

- Uses `allenai/olmOCR-2-7B-1025-FP8`, which is already quantized to FP8 and runs comfortably on a 6 GB RTX 4050 when `gpu_memory_utilization ≤ 0.6`.
- `ocr_module.OCRProcessor` talks to a local OpenAI-compatible endpoint (served via `vllm`). If you prefer a hosted provider (DeepInfra, Parasail, etc.) just change the `.env` values.
- `process.py` is a tiny CLI: pass one or more image paths and it prints the extracted text. No LLM cleaning/summarisation phases are left in the codebase.

## Requirements

| Component | Notes |
| --- | --- |
| Python 3.11+ | `olmocr` wheels target 3.11+ and include PyTorch 2.7. |
| GPU | RTX 4050 laptop GPU (6 GB) works with FP8 quantization. Larger cards can raise `gpu_memory_utilization`. |
| CUDA toolkit | Install NVIDIA drivers + CUDA 12.4 (or matching version for the `vllm` wheel you install). |
| System packages | `poppler-utils`, `libgl1`, `libgomp1`, fonts – covered automatically in Docker. |
| Hugging Face token | Required to download `allenai/olmOCR-2-7B-1025-FP8`. Set `HF_TOKEN` in `.env`. |

## Setup

```bash
python -m venv .venv
. .venv/bin/activate  # .\.venv\Scripts\activate on Windows
pip install --upgrade pip
pip install -r requirements.txt
```

### Launch the local vLLM server (quantized)

```powershell
pwsh scripts/start_local_olmocr.ps1
# or the equivalent bash script if you create one
```

The script simply runs:

```
vllm serve allenai/olmOCR-2-7B-1025-FP8 \
  --served-model-name olmocr \
  --quantization fp8 \
  --gpu-memory-utilization 0.6 \
  --port 30024
```

Set `HF_TOKEN` in your environment (or `.env`) so vLLM can download the checkpoint. Once the server prints “The server is fired up and ready to roll!” you can point `OCRProcessor` at `http://localhost:30024/v1`.

### Run OCR on local files

```bash
python process.py 01.png 02.png
```

Output example:

```
=== 01.png ===
[1.00] PATIENT: John Smith
[0.98] DOB: 07/12/1981
...
```

The confidence value is just a placeholder (olmOCR does not expose per-line scores).

### Process blobs from Postgres

Set the database credentials in `.env` (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS`). The `case_blob` table is expected to contain `cb_binary` (BYTEA) and `cb_filename` columns. Then call:

```bash
python process.py --blob-ids 1234 5678
```

Each blob entry in the JSON output includes the ID, filename, and per-page OCR results. PNG/JPG/SVG/PDF blobs are supported (PDFs are expanded into individual pages).

## Environment variables

`.env` ships with sensible defaults:

```
OLMOCR_SERVER_URL=http://127.0.0.1:30024/v1
OLMOCR_MODEL=olmocr
OLMOCR_GPU_MEMORY_UTILIZATION=0.6
OLMOCR_TARGET_LONGEST_DIM=1280
```

If you use a hosted provider, update `OLMOCR_SERVER_URL`, `OLMOCR_MODEL`, and `OLMOCR_API_KEY`.

For database usage, make sure `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASS` are filled in.

## Docker

Build & run (mount the model cache if you want re-use between runs):

```bash
docker build -t ocr-processor:latest .
docker run --rm --gpus all \
  --env-file .env \
  -v ${PWD}/models:/root/.cache/huggingface \
  ocr-processor:latest 01.png
```

Inside the container `python process.py` is executed. You still need a vLLM server reachable from the container (either host-port mapping or run the server in another container).

## Troubleshooting

- `HTTP 401/403` – `OLMOCR_API_KEY` or `HF_TOKEN` missing/invalid.
- `CUDA out of memory` – lower `OLMOCR_GPU_MEMORY_UTILIZATION`, shrink `OLMOCR_TARGET_LONGEST_DIM`, or limit concurrent requests.
- `finish_reason != stop` – the server restarted; `OCRProcessor` already retries with exponential backoff.
- `vllm` wheel install fails on Windows – install via WSL2 Ubuntu, or run the official [`alleninstituteforai/olmocr`](https://hub.docker.com/r/alleninstituteforai/olmocr) Docker image with `--gpus all`.

## Next steps

- Wire `process.py` into your database loader so the binary blobs feed directly into `OCRProcessor`.
- Tune the quantization / resolution knobs for your GPU (e.g., `--gpu-memory-utilization 0.7`, `OLMOCR_TARGET_LONGEST_DIM=1400` on 8 GB cards).
