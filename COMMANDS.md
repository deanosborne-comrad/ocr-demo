# Simple build and run

```bash
docker build -t ocr-processor:latest .
docker run --rm \
  --env-file .env \
  -v ${PWD}/images:/data \
  ocr-processor:latest /data/01.png
```

# Start all services

```bash
docker-compose up -d
```

# Build and start

```bash
docker-compose up --build
```

# Run CLI directly

```bash
python process.py 01.png 02.png
python process.py --blob-ids 1234 5678
```

# View logs

```bash
docker-compose logs -f ocr-processor
```

# Stop all services

```bash
docker-compose down
```

# Stop and remove volumes

```bash
docker-compose down -v
```

# Build with metadata

```bash
docker build \
  --build-arg BUILD_REV=$(git rev-parse --short HEAD) \
  --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
  -t ocr-processor:prod .
```

# Run with resource limits

```bash
docker run --rm \
  --cpus="2.0" \
  --memory="4g" \
  -e OMP_NUM_THREADS=8 \
  ocr-processor:latest /data/01.png
```
