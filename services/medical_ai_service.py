import re
import logging
from services.medical_file_service import MedicalFileService
from services.databricks_ai_service import DatabricksAIService

logger = logging.getLogger(__name__)


def _empty_ai_analysis() -> dict:
    return {
        "patient_info": {
            "name": None, "age": None, "gender": None,
            "patient_id": None, "contact": None,
            "blood_group": None, "allergies": [], "address": None
        },
        "diagnoses": [],
        "icd10_codes": [],
        "symptoms": [],
        "vital_signs": {
            "blood_pressure": None, "heart_rate": None,
            "temperature": None, "respiratory_rate": None,
            "oxygen_saturation": None, "weight": None,
            "height": None, "bmi": None
        },
        "lab_results": [],
        "current_medications": [],
        "medical_history": [],
        "abnormal_findings": [],
        "severity_level": "LOW",
        "clinical_suggestions": [],
        "summary": "",
        "analyzed_by": "",
        "model_used": "",
        "extraction_info": {
            "text_length": 0,
            "file_type": "",
            "extraction_successful": False,
            "extracted_text_preview": "",
            "ocr_quality_score": 0.0,
            "ocr_quality_warning": False,
            "ocr_quality_issues": []
        }
    }


class MedicalAIService:

    def __init__(self):
        self.file_service = MedicalFileService()
        self.databricks = DatabricksAIService()

    def analyze_report(self, file_content: bytes, file_type: str) -> dict:
        text = self.file_service.extract_text(file_content, file_type)
        quality_score, quality_issues = self._assess_ocr_quality(text)

        result = None
        # Try Databricks first
        if self.databricks.enabled:
            try:
                result = self.databricks.analyze_medical_text(text)
            except Exception as e:
                logger.warning(f"Databricks analysis failed, falling back to local: {e}")

        # Local fallback
        if result is None:
            result = self.analyze_medical_report(text)

        # Attach extraction_info
        result['extraction_info'] = {
            "text_length": len(text),
            "file_type": file_type,
            "extraction_successful": len(text) > 0,
            "extracted_text_preview": text[:500] if text else "",
            "ocr_quality_score": quality_score,
            "ocr_quality_warning": quality_score < 0.5,
            "ocr_quality_issues": quality_issues,
        }
        return result

    def _assess_ocr_quality(self, text: str) -> tuple[float, list[str]]:
        issues = []
        score = 1.0

        if len(text) < 50:
            return 0.0, ["Text too short — extraction likely failed"]

        total_chars = len(text)
        # Garbage char ratio
        garbage = sum(1 for c in text if not c.isprintable() and c not in '\n\r\t')
        garbage_ratio = garbage / total_chars if total_chars else 0
        if garbage_ratio > 0.30:
            score -= 0.5
            issues.append(f"High garbage character ratio: {garbage_ratio:.1%}")

        # Alpha ratio
        alpha = sum(1 for c in text if c.isalpha())
        alpha_ratio = alpha / total_chars if total_chars else 0
        if alpha_ratio < 0.20:
            score -= 0.3
            issues.append(f"Low alphabetic character ratio: {alpha_ratio:.1%}")

        # Word count vs char count
        words = text.split()
        word_count = len(words)
        expected_words = total_chars / 6  # avg word length ~6
        if word_count < expected_words * 0.3:
            score -= 0.4
            issues.append(f"Low word count relative to character count")
        elif word_count < expected_words * 0.5:
            score -= 0.2
            issues.append(f"Moderate word count relative to character count")

        return max(0.0, min(1.0, score)), issues

    def analyze_medical_report(self, text: str) -> dict:
        """Local regex-based extraction."""
        result = _empty_ai_analysis()
        result['analyzed_by'] = 'local'
        result['model_used'] = 'regex-pattern-matching'

        if not text:
            result['summary'] = 'No text could be extracted from the report.'
            return result

        t = text

        # Patient info
        name_m = re.search(r'(?:patient\s*name|name)\s*[:\-]?\s*([A-Za-z\s]+)', t, re.I)
        if name_m:
            result['patient_info']['name'] = name_m.group(1).strip()

        age_m = re.search(r'(?:age|years?\s*old)\s*[:\-]?\s*(\d{1,3})', t, re.I)
        if age_m:
            result['patient_info']['age'] = int(age_m.group(1))

        gender_m = re.search(r'(?:gender|sex)\s*[:\-]?\s*(male|female|m|f)\b', t, re.I)
        if gender_m:
            g = gender_m.group(1).lower()
            result['patient_info']['gender'] = 'Male' if g in ('m', 'male') else 'Female'

        pid_m = re.search(r'(?:patient\s*id|pid|mrn)\s*[:\-]?\s*([A-Za-z0-9\-]+)', t, re.I)
        if pid_m:
            result['patient_info']['patient_id'] = pid_m.group(1).strip()

        phone_m = re.search(r'(?:phone|contact|tel)\s*[:\-]?\s*([\d\s\-\+\(\)]{7,20})', t, re.I)
        if phone_m:
            result['patient_info']['contact'] = phone_m.group(1).strip()

        bg_m = re.search(r'(?:blood\s*group|blood\s*type)\s*[:\-]?\s*([ABO]{1,2}[+-]?)', t, re.I)
        if bg_m:
            result['patient_info']['blood_group'] = bg_m.group(1).strip()

        allergy_m = re.search(r'(?:allerg(?:y|ies))\s*[:\-]?\s*([^\n\.]+)', t, re.I)
        if allergy_m:
            allergies = [a.strip() for a in re.split(r'[,;]', allergy_m.group(1)) if a.strip()]
            result['patient_info']['allergies'] = allergies

        # Diagnoses
        diag_m = re.search(r'(?:diagnosis|diagnoses|impression|assessment)\s*[:\-]?\s*([^\n]+(?:\n(?!\n)[^\n]+)*)', t, re.I)
        if diag_m:
            diags = [d.strip() for d in re.split(r'[,;\n]', diag_m.group(1)) if d.strip() and len(d.strip()) > 2]
            result['diagnoses'] = diags[:10]

        # ICD-10 codes
        icd_codes = re.findall(r'\b([A-Z]\d{2}(?:\.\d{1,4})?)\b', t)
        result['icd10_codes'] = list(set(icd_codes))[:10]

        # Symptoms
        symp_m = re.search(r'(?:symptoms?|complaints?|presenting)\s*[:\-]?\s*([^\n]+(?:\n(?!\n)[^\n]+)*)', t, re.I)
        if symp_m:
            symptoms = [s.strip() for s in re.split(r'[,;\n]', symp_m.group(1)) if s.strip() and len(s.strip()) > 2]
            result['symptoms'] = symptoms[:10]

        # Vital signs
        bp_m = re.search(r'(?:bp|blood\s*pressure)\s*[:\-]?\s*(\d{2,3}\s*/\s*\d{2,3})', t, re.I)
        if bp_m:
            result['vital_signs']['blood_pressure'] = bp_m.group(1).replace(' ', '')

        hr_m = re.search(r'(?:hr|heart\s*rate|pulse)\s*[:\-]?\s*(\d{2,3})\s*(?:bpm)?', t, re.I)
        if hr_m:
            result['vital_signs']['heart_rate'] = int(hr_m.group(1))

        temp_m = re.search(r'(?:temp(?:erature)?)\s*[:\-]?\s*(\d{2,3}(?:\.\d)?)\s*(?:°?[CF])?', t, re.I)
        if temp_m:
            result['vital_signs']['temperature'] = float(temp_m.group(1))

        rr_m = re.search(r'(?:rr|respiratory\s*rate)\s*[:\-]?\s*(\d{1,2})', t, re.I)
        if rr_m:
            result['vital_signs']['respiratory_rate'] = int(rr_m.group(1))

        spo2_m = re.search(r'(?:spo2|o2\s*sat|oxygen\s*sat)\s*[:\-]?\s*(\d{2,3}(?:\.\d)?)\s*%?', t, re.I)
        if spo2_m:
            result['vital_signs']['oxygen_saturation'] = float(spo2_m.group(1))

        weight_m = re.search(r'(?:weight|wt)\s*[:\-]?\s*(\d{2,3}(?:\.\d)?)\s*(?:kg|lbs?)?', t, re.I)
        if weight_m:
            result['vital_signs']['weight'] = float(weight_m.group(1))

        height_m = re.search(r'(?:height|ht)\s*[:\-]?\s*(\d{2,3}(?:\.\d)?)\s*(?:cm|m|ft)?', t, re.I)
        if height_m:
            result['vital_signs']['height'] = float(height_m.group(1))

        bmi_m = re.search(r'(?:bmi|body\s*mass\s*index)\s*[:\-]?\s*(\d{2}(?:\.\d{1,2})?)', t, re.I)
        if bmi_m:
            result['vital_signs']['bmi'] = float(bmi_m.group(1))

        # Medications
        med_section = re.search(r'(?:medications?|drugs?|prescriptions?)\s*[:\-]?\s*([^\n]+(?:\n(?!\n)[^\n]+)*)', t, re.I)
        if med_section:
            med_lines = [l.strip() for l in med_section.group(1).split('\n') if l.strip()]
            for line in med_lines[:10]:
                parts = re.split(r'\s+', line, maxsplit=3)
                result['current_medications'].append({
                    "name": parts[0] if parts else line,
                    "dosage": parts[1] if len(parts) > 1 else "",
                    "frequency": parts[2] if len(parts) > 2 else "",
                    "duration": "",
                    "route": "",
                    "instructions": parts[3] if len(parts) > 3 else "",
                })

        # Medical history
        hist_m = re.search(r'(?:medical\s*history|past\s*history|pmh)\s*[:\-]?\s*([^\n]+(?:\n(?!\n)[^\n]+)*)', t, re.I)
        if hist_m:
            history = [h.strip() for h in re.split(r'[,;\n]', hist_m.group(1)) if h.strip() and len(h.strip()) > 2]
            result['medical_history'] = history[:10]

        # Abnormal findings
        abnormal_m = re.search(r'(?:abnormal|findings?|results?)\s*[:\-]?\s*([^\n]+(?:\n(?!\n)[^\n]+)*)', t, re.I)
        if abnormal_m:
            findings = [f.strip() for f in re.split(r'[,;\n]', abnormal_m.group(1)) if f.strip() and len(f.strip()) > 2]
            result['abnormal_findings'] = findings[:10]

        # Severity
        if re.search(r'\b(critical|emergency|severe|life.threatening)\b', t, re.I):
            result['severity_level'] = 'CRITICAL'
        elif re.search(r'\b(high|significant|serious|moderate.to.severe)\b', t, re.I):
            result['severity_level'] = 'HIGH'
        elif re.search(r'\b(moderate|mild.to.moderate)\b', t, re.I):
            result['severity_level'] = 'MEDIUM'
        else:
            result['severity_level'] = 'LOW'

        # Summary
        summary_m = re.search(r'(?:summary|conclusion|impression|plan)\s*[:\-]?\s*([^\n]+(?:\n(?!\n)[^\n]+)*)', t, re.I)
        if summary_m:
            result['summary'] = summary_m.group(1).strip()[:1000]
        else:
            result['summary'] = f"Medical report analyzed. Found {len(result['diagnoses'])} diagnosis/diagnoses."

        # Clinical suggestions based on severity
        if result['severity_level'] in ('HIGH', 'CRITICAL'):
            result['clinical_suggestions'].append({
                "category": "Urgent Care",
                "suggestion": "Immediate medical attention recommended based on severity indicators.",
                "confidence": 0.8,
                "priority": "HIGH",
                "reasoning": f"Severity level detected as {result['severity_level']}"
            })

        return result
