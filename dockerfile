FROM python:3.9-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make cmake poppler-utils libgl1 libgomp1 libglx-mesa0 libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip wheel setuptools && \
    pip install --no-cache-dir -r requirements.txt

COPY ./models/paddleocr /root/.paddleocr

RUN curl -fsSL https://ollama.ai/install.sh | sh
RUN ollama serve & sleep 15 && \
    ollama pull medllama2 && \
    ollama pull nomic-embed-text && \
    sleep 10 && pkill ollama

FROM python:3.9-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils libgl1 libglx-mesa0 libglib2.0-0 libgthread-2.0-0 \
    libsm6 libxext6 libxrender-dev libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://ollama.ai/install.sh | sh

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /root/.paddleocr /root/.paddleocr
COPY --from=builder /root/.ollama /root/.ollama

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    OLLAMA_HOST=0.0.0.0 \
    OLLAMA_KEEP_ALIVE=24h

WORKDIR /app
COPY ocr_module.py llm_module.py process.py .env ./

CMD ["sh", "-c", "ollama serve & sleep 10 && python process.py $@"]
