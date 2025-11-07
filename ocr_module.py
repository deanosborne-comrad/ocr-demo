import os
import logging
import re
import threading
from typing import List, Tuple, Optional
import numpy as np
import cv2
from paddleocr import PaddleOCR

logger = logging.getLogger(__name__)

NOISE_CHARS = frozenset('-.,;:\'"~_!@#$%^&*()[]{}<>?/\\|¿¡§¶†‡•‰€™')
ocr_lock = threading.Lock()

class OCRProcessor:
    def __init__(self):
        os.environ['OMP_NUM_THREADS'] = '1'
        os.environ['MKL_NUM_THREADS'] = '1'
        self.ocr = PaddleOCR(
            lang='en',
            det_db_thresh=0.1,
            det_db_box_thresh=0.3,
            det_db_unclip_ratio=2.5,
            rec_batch_num=1,
            max_text_length=100,
            drop_score=0.2,
            use_angle_cls=True,
            use_space_char=True,
            use_gpu=False,
            show_log=False
        )
    
    def validate_kernel_size(self, size):
        if size <= 0:
            return 1
        if size % 2 == 0:
            return size + 1
        return size
    
    def enhance_for_handwriting(self, image_np: np.ndarray) -> np.ndarray:
        if len(image_np.shape) == 3:
            gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
        else:
            gray = image_np.copy()
        
        kernel_size = self.validate_kernel_size(3)
        blurred = cv2.GaussianBlur(gray, (kernel_size, kernel_size), 0)
        
        adaptive_thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(adaptive_thresh, cv2.MORPH_CLOSE, kernel)
        
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (1, 1))
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel_open)
        
        if len(image_np.shape) == 3:
            return cv2.cvtColor(cleaned, cv2.COLOR_GRAY2RGB)
        return cleaned
    
    def pad_to_multiple(self, img: np.ndarray, multiple: int = 32) -> np.ndarray:
        h, w = img.shape[:2]
        new_h = (h + multiple - 1) // multiple * multiple
        new_w = (w + multiple - 1) // multiple * multiple
        if new_h != h or new_w != w:
            padded_img = np.zeros((new_h, new_w, 3), dtype=img.dtype)
            padded_img[:h, :w, :] = img
            return padded_img
        return img
    
    def preprocess_image(self, image_np: np.ndarray) -> np.ndarray:
        if len(image_np.shape) == 3:
            gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
        else:
            gray = image_np
        
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        img_rgb = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)
        return self.pad_to_multiple(img_rgb, multiple=32)
    
    def normalize_text(self, text: str) -> Optional[str]:
        if not text:
            return None
        
        text = text.strip()
        if not text:
            return None
        
        text = re.sub(r'[^\w\s\-.,;:\'"~!@#$%^&*()[\]{}<>?/\\|¿¡§¶†‡•‰€™]', '', text)
        text = text.strip()
        
        if len(text) == 1 and text in NOISE_CHARS:
            return None
        
        if len(text) >= 1 and (text.isalnum() or len(text) >= 2):
            return text
        
        return None
    
    def safe_ocr_process(self, image_np: np.ndarray, strategy_name: str) -> List[Tuple[str, float]]:
        try:
            with ocr_lock:
                raw_result = self.ocr.ocr(image_np, cls=True)
            
            if raw_result and raw_result[0]:
                results = []
                for line in raw_result[0]:
                    if not (isinstance(line, list) and len(line) == 2):
                        continue
                    text_info = line[1]
                    if not (isinstance(text_info, (tuple, list)) and len(text_info) == 2):
                        continue
                        
                    text, score = text_info
                    normalized_text = self.normalize_text(str(text))
                    
                    if normalized_text:
                        results.append((normalized_text, float(score)))
                
                logger.info(f"{strategy_name}: extracted {len(results)} texts")
                return results
            
        except Exception as e:
            logger.error(f"Error processing {strategy_name}: {e}")
            return []
        
        return []
    
    def merge_ocr_results(self, results_list: List[List[Tuple[str, float]]]) -> List[Tuple[str, float]]:
        text_scores = {}
        
        for results in results_list:
            for text, score in results:
                normalized = self.normalize_text(text)
                if normalized:
                    if normalized not in text_scores or score > text_scores[normalized]:
                        text_scores[normalized] = score
        
        return sorted(text_scores.items(), key=lambda x: x[1], reverse=True)
    
    def process_image(self, image_np: np.ndarray) -> List[Tuple[str, float]]:
        if len(image_np.shape) == 2:
            image_np = cv2.cvtColor(image_np, cv2.COLOR_GRAY2RGB)
        elif image_np.shape[2] == 4:
            image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2RGB)
        
        strategies = [
            ('original', lambda img: self.pad_to_multiple(img if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2RGB), 32)),
            ('enhanced', lambda img: self.preprocess_image(img)),
            ('handwriting', lambda img: self.pad_to_multiple(self.enhance_for_handwriting(img), 32))
        ]
        
        all_results = []
        for name, preprocess_func in strategies:
            try:
                processed = preprocess_func(image_np)
                if processed is not None and processed.size > 0:
                    results = self.safe_ocr_process(processed, name)
                    if results:
                        all_results.append(results)
            except Exception as e:
                logger.error(f"Error in {name} preprocessing: {e}")
        
        merged = self.merge_ocr_results(all_results)
        filtered = [(text, score) for text, score in merged if score >= 0.3]
        
        logger.info(f"OCR completed: {len(filtered)} unique items")
        return filtered
