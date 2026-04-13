import os
import json
import logging
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DATABRICKS_TOKEN = os.getenv('DATABRICKS_TOKEN', '')
DATABRICKS_API_URL = os.getenv('DATABRICKS_API_URL', '')
DATABRICKS_MODEL_ENDPOINT = os.getenv(
    'DATABRICKS_MODEL_ENDPOINT',
    '/serving-endpoints/databricks-meta-llama-3-1-8b-instruct/invocations'
)

class DatabricksAIService:
    """Service to interact with Databricks AI using ResumeBot-style structured extraction."""

    def __init__(self):
        self.enabled = bool(DATABRICKS_TOKEN and DATABRICKS_API_URL)
        self.endpoint = DATABRICKS_API_URL.rstrip('/') + DATABRICKS_MODEL_ENDPOINT

    def analyze_medical_report(self, file_content: bytes, file_type: str, extracted_text: str = None) -> dict:
        """
        Call Databricks AI to analyze medical report.
        If extracted_text is provided, uses TEXT mode (Llama 3.1 compatible).
        Otherwise uses VISION mode (Llama 3.2 Vision required).
        """
        if not self.enabled:
            raise RuntimeError("Databricks not configured. Please set DATABRICKS_TOKEN and DATABRICKS_API_URL.")

        system_prompt = (
            "You are a Clinical Analysis & Medical Data Expert. "
            "Your task is to accurately extract structured information from medical reports. "
            "Analyze the provided content and return a JSON object that strictly follows the specified schema. "
            "CRITICAL: The 'summary' field MUST be a professional, well-formatted Markdown summary. "
            "Use bold text for keys, bullet points for findings, and ensure a logical structure within the summary string. "
            "Focus on high precision for lab values, symptoms, and diagnoses."
        )

        json_schema = {
            "patient_info": {"name": None, "age": None, "gender": None, "patient_id": None, "contact": None, "blood_group": None},
            "diagnoses": [], "icd10_codes": [], "symptoms": [],
            "vital_signs": {"blood_pressure": None, "heart_rate": None, "temperature": None, "oxygen_saturation": None},
            "lab_results": [{"test_name": "", "value": "", "unit": "", "reference_range": "", "is_abnormal": False}],
            "current_medications": [{"name": "", "dosage": "", "frequency": "", "instructions": ""}],
            "medical_history": [], "abnormal_findings": [], "severity_level": "LOW | MEDIUM | HIGH | CRITICAL", "summary": ""
        }

        if extracted_text:
            user_content = (
                f"Please process the following medical report text and extract detailed JSON information based on this schema: {json.dumps(json_schema)}\n\n"
                f"## MEDICAL REPORT TEXT:\n{extracted_text}\n\n"
                f"Respond with ONLY the JSON object."
            )
        else:
            encoded_image = base64.b64encode(file_content).decode('utf-8')
            mime_type = "application/pdf" if file_type.lower() == "pdf" else f"image/{file_type.lower()}"
            if file_type.lower() in ("jpg", "jpeg"):
                mime_type = "image/jpeg"

            user_content = [
                {"type": "text", "text": f"Analyze the report document and return structured JSON following this schema: {json.dumps(json_schema)}"},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded_image}"}}
            ]

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 4096,
            "temperature": 0.1,
        }

        headers = {
            "Authorization": f"Bearer {DATABRICKS_TOKEN}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(self.endpoint, json=payload, headers=headers, timeout=90)
            response.raise_for_status()

            data = response.json()
            content = data['choices'][0]['message']['content']
            logger.info(f"AI Response Content: {content[:100]}...")

            try:
                start_idx = content.find('{')
                end_idx = content.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    json_str = content[start_idx : end_idx + 1].strip()
                else:
                    json_str = content.strip()

                result = json.loads(json_str)
            except json.JSONDecodeError as je:
                logger.error(f"JSON Parsing failed. Raw Content: {content}")
                raise ValueError(f"AI returned invalid JSON: {str(je)}")

            result['analyzed_by'] = 'databricks'
            result['model_used'] = DATABRICKS_MODEL_ENDPOINT
            return result
        except Exception as e:
            logger.error(f"Databricks analysis failed: {e}")
            raise

    def answer_question_with_context(self, context: str, analysis: dict, history: list[dict], question: str, language: str = "English") -> str:
        """
        High-quality chat about the medical report.
        Uses both raw text and structured analysis for context.
        """
        if not self.enabled:
            return "Databricks AI not configured."

        analysis_str = json.dumps(analysis, indent=2) if analysis else "No structured analysis available."
        
        messages = [
            {
                "role": "system", 
                "content": (
                    "You are a professional Medical AI Assistant. Answer the patient's questions about their report. "
                    "Use the Provided Context (Extracted Text) and the Structured Analysis below. "
                    f"CRITICAL: You MUST respond strictly in {language}. "
                    f"If the user asks in English but the target language is {language}, translate your thoughts into {language} for the final response. "
                    "CRITICAL FORMATTING INSTRUCTIONS:\n"
                    "1. Use clear Markdown headers (# ## ###).\n"
                    "2. Use Tables for any lab results or comparisons.\n"
                    "3. Use **Bold** for symptoms, diagnoses, and important medical terms.\n"
                    "4. Use bullet points for lists.\n"
                    "5. Ensure the response looks professional, empathetic, and extremely well-organized.\n"
                    "If the information is not in the context, politely state that you cannot find it in this specific report."
                )
            },
            {
                "role": "user", 
                "content": (
                    f"## CONTEXT (Extracted Text):\n{context}\n\n"
                    f"## STRUCTURED ANALYSIS (JSON):\n{analysis_str}\n\n"
                    f"The patient is asking: {question}"
                )
            }
        ]
        
        for msg in history[:-1]:
            messages.insert(-1, {"role": msg['role'], "content": msg['content']})

        payload = {"messages": messages, "max_tokens": 1500, "temperature": 0.1}
        headers = {"Authorization": f"Bearer {DATABRICKS_TOKEN}", "Content-Type": "application/json"}

        try:
            response = requests.post(self.endpoint, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content'].strip()
        except Exception as e:
            logger.error(f"Databricks answer failed: {e}")
            return f"I'm sorry, I encountered an error while processing your request: {str(e)}"

    def get_medicine_info(self, medicine_name: str) -> dict:
        """
        Fetch detailed information about a medicine using AI.
        """
        if not self.enabled:
            raise RuntimeError("Databricks not configured.")

        system_prompt = (
            "You are a helpful Medical Assistant. "
            "Your task is to provide extremely simple, easy-to-understand information about medicines for regular patients. "
            "AVOID medical jargon. Use plain English that a 10-year-old could understand. "
            "Return a JSON object that strictly follows the specified schema."
        )

        json_schema = {
            "medicine_name": medicine_name,
            "benefits": ["Simple benefit 1", "Simple benefit 2"],
            "side_effects": ["Simple side effect 1", "Simple side effect 2"],
            "dosage_timing": "Simple timing (e.g., Every morning after you eat)",
            "when_to_avoid": ["Simple warning 1", "Simple warning 2"],
            "professional_summary": "A very simple explanation of what this medicine does."
        }

        user_content = (
            f"Explain this medicine in very simple words: **{medicine_name}**\n"
            f"Format it as JSON: {json.dumps(json_schema)}\n"
            "Use only common words. No complex medical terms. Respond with ONLY the JSON object."
        )

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 2048,
            "temperature": 0.1,
        }

        headers = {
            "Authorization": f"Bearer {DATABRICKS_TOKEN}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(self.endpoint, json=payload, headers=headers, timeout=60)
            response.raise_for_status()

            data = response.json()
            content = data['choices'][0]['message']['content']
            
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            if start_idx != -1 and end_idx != -1:
                json_str = content[start_idx : end_idx + 1].strip()
            else:
                json_str = content.strip()

            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Failed to get medicine info for {medicine_name}: {e}")
            raise
