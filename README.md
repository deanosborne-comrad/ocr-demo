Excellent. Fetching the binary data directly from a PostgreSQL database is a much more robust and scalable approach than reading from a local file system.

We will modify the solution to connect to your PostgreSQL database, query the case_blob table, retrieve the binary data from the cb_binary column, and then perform the OCR.

Database Schema Assumption

For this solution to work, I'll make a small but important assumption about your case_blob table. To know how to process the binary data (as a PNG, PDF, etc.), the script needs some metadata. The best way to store this is in another column.

I will assume your table looks something like this, with a primary key and a column to store the original filename or mime type:
SQL

CREATE TABLE case_blob (
id SERIAL PRIMARY KEY, -- A unique identifier for the row
cb_filename VARCHAR(255), -- The original filename, e.g., 'invoice.pdf' or 'photo.png'
cb_binary BYTEA -- The binary data of the file
);

The script will use the cb_filename column to determine the file type. If you store a MIME type (e.g., application/pdf) instead, the code can be easily adapted.

Step 1: Update requirements.txt

We need to add a PostgreSQL driver. psycopg2-binary is the standard choice and is easy to install.

requirements.txt
Plaintext

paddlepaddle
paddleocr
Pillow
numpy
pdf2image
CairoSVG
psycopg2-binary

Step 2: Update The Python Script (ocr_processor.py)

The script will now connect to the database using credentials provided via environment variables (a security best practice), fetch the blob, and then proceed with the same processing logic as before.

ocr_processor.py (Updated Version)
Python

import sys
import io
import os
import numpy as np
from PIL import Image
from paddleocr import PaddleOCR
from pdf2image import convert_from_bytes
import cairosvg
import psycopg2 # NEW: For connecting to PostgreSQL

# --- Initialize PaddleOCR ---

# This is done once and reused.

print("Initializing PaddleOCR...")
ocr = PaddleOCR(use_angle_cls=True, lang="en")
print("PaddleOCR Initialized.")

# --- Database Connection ---

# NEW: Fetch credentials from environment variables for security

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

def fetch_blob_from_db(blob_id):
"""
Connects to the database and fetches the binary data and filename for a given ID.
"""
conn = None
try:
if not all([DB_NAME, DB_USER, DB_PASS]):
raise ValueError("Database credentials (DB_NAME, DB_USER, DB_PASS) must be set as environment variables.")

        print(f"Connecting to database '{DB_NAME}' on {DB_HOST}:{DB_PORT}...")
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        cur = conn.cursor()

        # Assumes your primary key is 'id' and filename column is 'cb_filename'
        query = "SELECT cb_binary, cb_filename FROM case_blob WHERE id = %s"
        cur.execute(query, (blob_id,))

        record = cur.fetchone()

        if record:
            print(f"Record found for ID {blob_id}.")
            binary_data, filename = record
            # The data from BYTEA is returned as a memoryview or bytes object, which is perfect.
            return binary_data, filename
        else:
            print(f"No record found for ID {blob_id}.")
            return None, None

    except Exception as e:
        print(f"Database error: {e}")
        return None, None
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

# --- Processing Functions (No changes needed here) ---

# process_image_binary, process_pdf_binary, process_svg_binary, print_ocr_results

# remain exactly the same as in the previous answer.

def process_image_binary(binary_data):
try:
image = Image.open(io.BytesIO(binary_data)).convert("RGB")
image_np = np.array(image)
return ocr.ocr(image_np, cls=True)
except Exception as e:
print(f"Error processing image binary: {e}")
return None

def process_pdf_binary(binary_data):
try:
images = convert_from_bytes(binary_data, dpi=300)
all_results = []
for i, page_image in enumerate(images):
print(f"--- Processing PDF Page {i+1} ---")
page_image_np = np.array(page_image)
result = ocr.ocr(page_image_np, cls=True)
all_results.append({"page": i + 1, "results": result})
return all_results
except Exception as e:
print(f"Error processing PDF binary: {e}")
return None

def process_svg_binary(binary_data):
try:
png_binary = cairosvg.svg2png(bytestring=binary_data)
return process_image_binary(png_binary)
except Exception as e:
print(f"Error processing SVG binary: {e}")
return None

def print_ocr_results(ocr_result):
if not ocr_result:
print("No results to print.")
return
if isinstance(ocr_result, list) and all(isinstance(item, dict) and 'page' in item for item in ocr_result):
for page_result in ocr_result:
print(f"\n============== Page {page_result['page']} ==============")
for page_data in page_result['results']:
for line in page_data:
text = line[1][0]
confidence = line[1][1]
print(f"Text: '{text}', Confidence: {confidence:.4f}")
else:
for result_set in ocr_result:
for line in result_set:
text = line[1][0]
confidence = line[1][1]
print(f"Text: '{text}', Confidence: {confidence:.4f}")

# --- Main execution block ---

if **name** == "**main**":
if len(sys.argv) < 2:
print("Usage: python ocr_processor.py <case_blob_id>")
sys.exit(1)

    try:
        target_id = int(sys.argv[1])
    except ValueError:
        print("Error: The provided ID must be an integer.")
        sys.exit(1)

    print(f"\nAttempting to fetch and process blob with ID: {target_id}")

    # NEW: Fetch data from the database
    binary_content, filename = fetch_blob_from_db(target_id)

    if binary_content and filename:
        results = None
        # Determine file type from filename and process
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            results = process_image_binary(binary_content)
        elif filename.lower().endswith('.pdf'):
            results = process_pdf_binary(binary_content)
        elif filename.lower().endswith('.svg'):
            results = process_svg_binary(binary_content)
        else:
            print(f"Unsupported file type for filename: {filename}")

        if results:
            print("\n--- OCR Results ---")
            print_ocr_results(results)
    else:
        print("Could not retrieve data from database. Aborting.")

Step 3: Dockerfile (No Changes)

Your Dockerfile from the previous step is perfectly fine. It will now install psycopg2-binary along with the other dependencies when it runs pip install -r requirements.txt.

Dockerfile (remains the same)
Dockerfile

FROM python:3.9-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
 poppler-utils \
 libgl1-mesa-glx \
 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/\*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ocr_processor.py .
ENTRYPOINT ["python", "ocr_processor.py"]

Step 4: Build and Run with Database Connection

The build process is the same, but the run command is different. We no longer need to mount a volume. Instead, we pass the database credentials and network configuration as parameters.

    Build the Docker image (or rebuild it if you built it previously):
    Bash

docker build -t paddleocr-service-db .

Run the container with Environment Variables:
You now pass your database credentials using the -e flag and provide the ID of the blob you want to process.
Bash

    docker run --rm \
      -e DB_HOST='your_db_host' \
      -e DB_PORT='5432' \
      -e DB_NAME='your_db_name' \
      -e DB_USER='your_username' \
      -e DB_PASS='your_password' \
      paddleocr-service-db 123

    (Replace 123 with the actual ID from your case_blob table).

Important Note on Docker Networking

How the container connects to your_db_host is critical:

    If your PostgreSQL is also a Docker container: Put both containers on the same Docker network and use the PostgreSQL container's name as the DB_HOST.

    If PostgreSQL is running on your host machine (the same machine running Docker):

        On Docker Desktop (Windows/Mac), you can use the special DNS name host.docker.internal as the DB_HOST.

        On Linux, the easiest way is to use host networking by adding --network="host" to the docker run command. In this case, DB_HOST would be localhost.

Example for Docker Desktop (DB on host):
Bash

docker run --rm \
 -e DB_HOST='host.docker.internal' \
 -e DB_PORT='5432' \
 -e DB_NAME='your_db_name' \
 -e DB_USER='your_username' \
 -e DB_PASS='your_password' \
 paddleocr-service-db 123

Step 5: Build and Run the Docker Container

Now, let's put it all together.

    Open your terminal and navigate to the ocr_service directory.

    Build the Docker image. This will take some time, especially the first time, as it downloads the base image and all dependencies.
    Bash

docker build -t paddleocr-service .

Run the container. We will use a volume (-v) to mount the test_files directory from your computer into the container at /app/test_files. This allows the script inside the container to access your local files.

To process a PNG file:
Bash

docker run --rm -v "$(pwd)/test_files:/app/test_files" paddleocr-service ./test_files/my_image.png

To process a PDF file:
Bash

docker run --rm -v "$(pwd)/test_files:/app/test_files" paddleocr-service ./test_files/my_document.pdf

To process an SVG file:
Bash

    docker run --rm -v "$(pwd)/test_files:/app/test_files" paddleocr-service ./test_files/my_vector.svg

When you run these commands, you will see output in your terminal as PaddleOCR initializes, processes the file, and finally prints the extracted text to the console.
