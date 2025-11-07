# Simple build and run

docker build -t ocr-processor:latest .
docker run --rm ocr-processor:latest <id>

# Start all services

docker-compose up -d

# Build and start

docker-compose up --build

# Run with specific blob ID

docker-compose run --rm ocr-processor <id>

# View logs

docker-compose logs -f ocr-processor

# Stop all services

docker-compose down

# Stop and remove volumes

docker-compose down -v

# Build with metadata

docker build \
 --build-arg BUILD_REV=$(git rev-parse --short HEAD) \
  --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
 -t ocr-processor:prod .

# Run with resource limits

docker run --rm \
 --cpus="2.0" \
 --memory="4g" \
 -e OMP_NUM_THREADS=8 \
 ocr-processor:latest 12345
