import json
import re
import logging
import threading
from typing import Dict, List, Any
import ollama

logger = logging.getLogger(__name__)
llm_lock = threading.Lock()

class LLMProcessor:
    def __init__(self, model_name="medllama2"):
        self.model_name = model_name
        self._ensure_models_available()
    
    def _ensure_models_available(self):
        try:
            models = ollama.list()
            available_models = [model['name'] for model in models['models']]
            
            if self.model_name not in available_models:
                logger.info(f"Pulling {self.model_name} model...")
                ollama.pull(self.model_name)
                logger.info(f"Model {self.model_name} cached locally")
            else:
                logger.info(f"Model {self.model_name} already available locally")
                
        except Exception as e:
            logger.error(f"Error setting up {self.model_name}: {e}")
            try:
                self.model_name = "llama3.2:3b"
                ollama.pull(self.model_name)
                logger.info(f"Fallback model {self.model_name} ready")
            except Exception as e2:
                logger.error(f"Failed to setup any model: {e2}")
                raise
    
    def generate_response(self, system_prompt: str, user_prompt: str, temperature: float = 0.1, max_tokens: int = 500) -> str:
        try:
            with llm_lock:
                response = ollama.generate(
                    model=self.model_name,
                    prompt=f"System: {system_prompt}\n\nUser: {user_prompt}",
                    options={'temperature': temperature, 'num_predict': max_tokens}
                )
            
            return response['response'].strip()
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return ""
    
    def clean_ocr_text(self, ocr_results: List[tuple]) -> str:
        if not ocr_results:
            return ""
        
        raw_text = " ".join([text for text, _ in ocr_results])
        
        system_prompt = """You are a medical document OCR correction specialist. Fix OCR errors in medical text while preserving medical terminology and meaning. Common OCR errors could include 'rn' -> 'm', 'cl' -> 'd', '6' -> 'G', 'li' -> 'h'. Return only the corrected text."""

        user_prompt = f"Correct OCR errors in this medical text:\n\n{raw_text}\n\nCorrected text:"
        
        try:
            cleaned_text = self.generate_response(system_prompt, user_prompt, temperature=0.1, max_tokens=500)
            logger.info(f"OCR text cleaned: {len(raw_text)} -> {len(cleaned_text)} chars")
            return cleaned_text
            
        except Exception as e:
            logger.error(f"Error cleaning OCR text: {e}")
            return raw_text
    
    def extract_medical_structure(self, text: str) -> Dict[str, Any]:
        if not text:
            return {"error": "No text provided"}
        
        system_prompt = """You are a medical information extraction specialist. Extract structured information from medical documents and return valid JSON. Extract these fields if present: patient_name, patient_id, date_of_service, referring_physician, medications, symptoms, diagnosis, procedures, vital_signs, clinical_notes, recommendations. Return only valid JSON."""

        user_prompt = f"Extract medical information from this text and return as JSON:\n\n{text}\n\nJSON:"

        try:
            response_text = self.generate_response(system_prompt, user_prompt, temperature=0.2, max_tokens=800)
            
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                try:
                    structured_data = json.loads(json_text)
                    logger.info("Successfully extracted structured medical data")
                    return structured_data
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON decode error: {e}")
            
            return {"raw_extraction": response_text}
            
        except Exception as e:
            logger.error(f"Error extracting medical structure: {e}")
            return {"error": str(e), "raw_text": text}
    
    def validate_medical_terms(self, text: str) -> Dict[str, Any]:
        if not text:
            return {"error": "No text provided"}
        
        system_prompt = """You are a medical terminology expert. Analyze medical text and identify expanded abbreviations, potential OCR errors, corrections suggested, and validated terms. Return JSON format."""

        user_prompt = f"Analyze this medical text for terminology issues:\n\n{text}\n\nAnalysis (JSON):"
        
        try:
            response_text = self.generate_response(system_prompt, user_prompt, temperature=0.1, max_tokens=600)
            
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                try:
                    return json.loads(response_text[json_start:json_end])
                except json.JSONDecodeError:
                    pass
            
            return {"analysis": response_text}
            
        except Exception as e:
            logger.error(f"Error validating medical terms: {e}")
            return {"error": str(e)}
    
    def summarize_document(self, text: str) -> str:
        if not text:
            return "No content to summarize."
        
        system_prompt = """You are a medical documentation specialist. Create concise, professional summaries of medical documents focusing on key medical findings, patient condition, medications and treatments, follow-up requirements, and critical information for healthcare providers."""

        user_prompt = f"Summarize this medical document:\n\n{text}\n\nSummary:"
        
        try:
            summary = self.generate_response(system_prompt, user_prompt, temperature=0.3, max_tokens=400)
            logger.info(f"Generated summary ({len(summary)} chars)")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return f"Summary generation failed: {str(e)}"
