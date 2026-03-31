import os
import json
import logging
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

    def __init__(self):
        self.enabled = bool(DATABRICKS_TOKEN and DATABRICKS_API_URL)
        self.endpoint = DATABRICKS_API_URL.rstrip('/') + DATABRICKS_MODEL_ENDPOINT

    def analyze_medical_text(self, text: str) -> dict:
        """
        Call Databricks LLM to analyze medical text.
        Raises exception on any error — caller handles fallback.
        """
        if not self.enabled:
            raise RuntimeError("Databricks not configured")

        system_prompt = (
            "You are a medical report analysis expert. "
            "Extract structured medical data from the provided report text. "
            "Return ONLY valid JSON matching the ai_analysis schema exactly."
        )
        user_prompt = (
            f"Analyze the following medical report and return structured JSON:\n\n{text}\n\n"
            "Return JSON with keys: patient_info, diagnoses, icd10_codes, symptoms, "
            "vital_signs, lab_results, current_medications, medical_history, "
            "abnormal_findings, severity_level, clinical_suggestions, summary."
        )

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 4096,
            "temperature": 0.1,
        }

        headers = {
            "Authorization": f"Bearer {DATABRICKS_TOKEN}",
            "Content-Type": "application/json",
        }

        response = requests.post(self.endpoint, json=payload, headers=headers, timeout=60)
        response.raise_for_status()

        data = response.json()
        content = data['choices'][0]['message']['content']

        # Extract JSON from response (may be wrapped in markdown code block)
        json_str = content
        if '```json' in content:
            json_str = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            json_str = content.split('```')[1].split('```')[0].strip()

        result = json.loads(json_str)
        result['analyzed_by'] = 'databricks'
        result['model_used'] = 'databricks-meta-llama-3-1-8b-instruct'
        return result
