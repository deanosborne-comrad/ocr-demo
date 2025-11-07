# This is a direct call to PaddlePaddle's API for demoing.
# If you use this, be aware of what is being passed. 
from paddleocr import PaddleOCR
ocr = PaddleOCR(
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=True,
    lang="en")

result = ocr.predict(
    input="./02.png")

for res in result:
    res.print()