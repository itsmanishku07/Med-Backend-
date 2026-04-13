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
        
        if not final_text:
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

            elif file_type.lower() in ('jpg', 'jpeg', 'png'):
                try:
                    from PIL import Image
                    import pytesseract
                    
                    img = Image.open(io.BytesIO(file_content))
                    raw_text = pytesseract.image_to_string(img)
                    final_text = clean_medical_text(raw_text)
                    logger.info(f"Image OCR extraction success. Length: {len(final_text)}")
                except Exception as e:
                    logger.warning(f"Local Image OCR failed: {e}. AI will attempt Cloud Vision.")

        try:
            result = self.databricks.analyze_medical_report(file_content, file_type, final_text)
            
            summary = result.get('summary', 'Report analyzed via Databricks AI.')
            
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

    def ask_question_about_report(self, context: str, analysis: dict, history: list[dict], question: str, language: str = "English") -> str:
        """
        Answers user questions using the extracted report context and structured analysis.
        """
        return self.databricks.answer_question_with_context(context, analysis, history, question, language)
