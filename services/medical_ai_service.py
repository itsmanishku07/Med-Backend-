import io
import logging
from services.databricks_ai_service import DatabricksAIService
from utils.text_utils import clean_medical_text

logger = logging.getLogger(__name__)

class MedicalAIService:
    """
    Orchestrates medical report analysis using the ResumeBot architecture.
    Handles PDFs locally (lite) and Images via Vision.
    """

    def __init__(self):
        self.databricks = DatabricksAIService()

    def analyze_report(self, file_content: bytes, file_type: str, existing_text: str = None) -> dict:
        """
        Main entry point for report analysis.
        If existing_text is provided, it skips extraction and goes straight to reasoning.
        """
        final_text = existing_text
        
        # 1. Local Parsing (Lite Extraction)
        if not final_text:
            # Case A: PDF extraction
            if file_type.lower() == 'pdf':
                try:
                    import PyPDF2
                    reader = PyPDF2.PdfReader(io.BytesIO(file_content))
                    text_parts = []
                    for page in reader.pages:
                        text_parts.append(page.extract_text() or '')
                    
                    raw_text = '\n'.join(text_parts)
                    final_text = clean_medical_text(raw_text)
                    logger.info(f"PDF local extraction success. Length: {len(final_text)}")
                except Exception as e:
                    logger.warning(f"PyPDF2 extraction failed: {e}")

            # Case B: Image OCR (JPG, PNG)
            elif file_type.lower() in ('jpg', 'jpeg', 'png'):
                try:
                    from PIL import Image
                    import pytesseract
                    import shutil
                    
                    # Proactively check if tesseract is available
                    if not shutil.which("tesseract"):
                        logger.warning("tesseract binary not found in PATH.")
                        raise EnvironmentError("Tesseract OCR engine is not installed on this system.")
                    
                    img = Image.open(io.BytesIO(file_content))
                    # Perform OCR
                    raw_text = pytesseract.image_to_string(img)
                    final_text = clean_medical_text(raw_text)
                    logger.info(f"Image OCR extraction success. Length: {len(final_text)}")
                except Exception as e:
                    logger.warning(f"Local Image OCR failed: {e}. AI will attempt Cloud Vision fallback.")

        try:
            # 2. AI Analysis (Uses Text Mode if final_text exists, else Vision Mode)
            # If it's an image and no text is available, Llama 3.1 8b will fail with 400 (Expected).
            result = self.databricks.analyze_medical_report(file_content, file_type, final_text)
            
            # Use summary or default for full_text compatibility
            summary = result.get('summary', 'Report analyzed via Databricks AI.')
            
            # Add extraction metadata for the UI
            result['extraction_info'] = {
                "text_length": len(final_text) if final_text else 0,
                "file_type": file_type,
                "extraction_successful": True,
                "model_used": self.databricks.endpoint.split('/')[-2],
                "ocr_mode": "existing_text" if existing_text else ("local_lite_pdf" if final_text else "cloud_vision")
            }
            
            return result, final_text if final_text else summary
            
        except Exception as e:
            logger.error(f"MedicalAIService.analyze_report failed: {e}")
            raise

    def ask_question_about_report(self, context: str, analysis: dict, history: list[dict], question: str) -> str:
        """
        Answers user questions using the extracted report context and structured analysis.
        """
        return self.databricks.answer_question_with_context(context, analysis, history, question)
