import re
import ast
import logging
from services.medical_file_service import MedicalFileService
from services.databricks_ai_service import DatabricksAIService

logger = logging.getLogger(__name__)

# Lines that are clearly table headers/separators, not medical content
_JUNK_PATTERNS = re.compile(
    r'^[\s\-\|=_*#~]+$'                          # separator lines
    r'|^\s*\|.*\|.*\|\s*$'                        # table rows with pipes
    r'|^[\d\s\.\,\-\|\/\(\)]+$'                  # pure numbers/symbols
    r'|(?:units|bio.?ref|interval|interpretation' # column headers
    r'|ref\.?\s*range|normal\s*range'
    r'|test\s*name|results?|method|technique'
    r'|collected|reported|processed|sector'
    r'|production|national|reference\s*lab'
    r'|block[\s\-]?[a-z]|rohini|delhi)',
    re.I
)

def _is_valid_medical_text(text: str, min_len: int = 5) -> bool:
    """Return True only if text looks like real medical content."""
    t = text.strip()
    if len(t) < min_len:
        return False
    if _JUNK_PATTERNS.search(t):
        return False
    # Must contain at least one letter
    if not any(c.isalpha() for c in t):
        return False
    # Reject lines that are mostly special chars
    special = sum(1 for c in t if not c.isalnum() and c not in ' .,()-/')
    if special / max(len(t), 1) > 0.4:
        return False
    return True


def _try_parse_dict_string(s: str) -> dict | None:
    """Try to parse a Python-style dict string like {'key': 'val'}."""
    try:
        val = ast.literal_eval(s.strip())
        if isinstance(val, dict):
            return val
    except Exception:
        pass
    return None


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
            "text_length": 0, "file_type": "",
            "extraction_successful": False,
            "extracted_text_preview": "",
            "ocr_quality_score": 0.0,
            "ocr_quality_warning": False,
            "ocr_quality_issues": []
        }
    }


def _normalize_lab(lab: dict) -> dict:
    return {
        'test_name':        str(lab.get('test_name') or lab.get('name') or ''),
        'value':            str(lab.get('value') or lab.get('result') or lab.get('results') or ''),
        'unit':             str(lab.get('unit') or lab.get('units') or ''),
        'reference_range':  str(lab.get('reference_range') or lab.get('bio_ref_interval') or lab.get('ref_range') or ''),
        'is_abnormal':      bool(lab.get('is_abnormal') or lab.get('abnormal') or False),
        'abnormality_type': str(lab.get('abnormality_type') or lab.get('interpretation') or lab.get('flag') or ''),
    }


class MedicalAIService:

    def __init__(self):
        self.file_service = MedicalFileService()
        self.databricks = DatabricksAIService()

    def _normalize_result(self, result: dict) -> dict:
        """Normalize AI result — handles field name variants and stringified dicts."""
        if not isinstance(result, dict):
            return _empty_ai_analysis()

        base = _empty_ai_analysis()

        # Scalar fields
        for key in ('severity_level', 'summary', 'analyzed_by', 'model_used'):
            if result.get(key):
                base[key] = result[key]

        valid_severities = ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
        if base['severity_level'] not in valid_severities:
            base['severity_level'] = 'LOW'

        # patient_info
        pi = result.get('patient_info') or {}
        if isinstance(pi, dict):
            for k, v in pi.items():
                if k in base['patient_info'] and not isinstance(v, (dict, list)):
                    base['patient_info'][k] = v

        # vital_signs
        vs = result.get('vital_signs') or {}
        if isinstance(vs, dict):
            for k, v in vs.items():
                if k in base['vital_signs'] and not isinstance(v, (dict, list)):
                    base['vital_signs'][k] = v

        # lab_results — also rescue dicts that ended up in other list fields
        rescued_labs = []
        lab_list = result.get('lab_results') or []
        for lab in lab_list:
            if isinstance(lab, dict):
                rescued_labs.append(_normalize_lab(lab))
            elif isinstance(lab, str):
                parsed = _try_parse_dict_string(lab)
                if parsed:
                    rescued_labs.append(_normalize_lab(parsed))

        # Simple text list fields — filter junk AND rescue any dicts
        for key in ('diagnoses', 'icd10_codes', 'symptoms', 'abnormal_findings', 'medical_history'):
            raw = result.get(key) or []
            clean = []
            for item in raw:
                if isinstance(item, dict):
                    # Dict ended up in a text field — rescue as lab result
                    rescued_labs.append(_normalize_lab(item))
                elif isinstance(item, str):
                    parsed = _try_parse_dict_string(item)
                    if parsed:
                        rescued_labs.append(_normalize_lab(parsed))
                    elif _is_valid_medical_text(item, min_len=4):
                        clean.append(item.strip())
            base[key] = clean

        base['lab_results'] = rescued_labs

        # current_medications
        med_list = result.get('current_medications') or []
        for med in med_list:
            if isinstance(med, dict):
                base['current_medications'].append({
                    'name':         str(med.get('name') or med.get('drug_name') or med.get('medication') or ''),
                    'dosage':       str(med.get('dosage') or med.get('dose') or ''),
                    'frequency':    str(med.get('frequency') or med.get('freq') or ''),
                    'duration':     str(med.get('duration') or ''),
                    'route':        str(med.get('route') or ''),
                    'instructions': str(med.get('instructions') or med.get('notes') or ''),
                })

        # clinical_suggestions
        sugg_list = result.get('clinical_suggestions') or []
        for s in sugg_list:
            if isinstance(s, dict):
                base['clinical_suggestions'].append({
                    'category':   str(s.get('category') or ''),
                    'suggestion': str(s.get('suggestion') or s.get('text') or ''),
                    'confidence': float(s.get('confidence') or 0.0),
                    'priority':   str(s.get('priority') or ''),
                    'reasoning':  str(s.get('reasoning') or ''),
                })

        return base

    def analyze_report(self, file_content: bytes, file_type: str) -> dict:
        text = self.file_service.extract_text(file_content, file_type)
        quality_score, quality_issues = self._assess_ocr_quality(text)

        result = None
        if self.databricks.enabled:
            try:
                result = self.databricks.analyze_medical_text(text)
            except Exception as e:
                logger.warning(f"Databricks failed, falling back to local: {e}")

        if result is None:
            result = self.analyze_medical_report(text)

        result = self._normalize_result(result)

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
            return 0.0, ["Text too short"]
        total = len(text)
        garbage = sum(1 for c in text if not c.isprintable() and c not in '\n\r\t')
        if garbage / total > 0.30:
            score -= 0.5
            issues.append(f"High garbage ratio: {garbage/total:.1%}")
        alpha = sum(1 for c in text if c.isalpha())
        if alpha / total < 0.20:
            score -= 0.3
            issues.append(f"Low alpha ratio: {alpha/total:.1%}")
        words = text.split()
        expected = total / 6
        if len(words) < expected * 0.3:
            score -= 0.4
            issues.append("Low word count")
        elif len(words) < expected * 0.5:
            score -= 0.2
            issues.append("Moderate word count")
        return max(0.0, min(1.0, score)), issues

    def analyze_medical_report(self, text: str) -> dict:
        """Local regex-based extraction with lab table parsing."""
        result = _empty_ai_analysis()
        result['analyzed_by'] = 'local'
        result['model_used'] = 'regex-pattern-matching'

        if not text:
            result['summary'] = 'No text could be extracted from the report.'
            return result

        t = text

        # ── Patient info ──────────────────────────────────────────────────────
        name_m = re.search(r'(?:patient\s*name|name)\s*[:\-]?\s*([A-Za-z][A-Za-z\s]{1,40})', t, re.I)
        if name_m:
            name = name_m.group(1).strip()
            if _is_valid_medical_text(name, 2):
                result['patient_info']['name'] = name

        age_m = re.search(r'\bage\s*[:\-]?\s*(\d{1,3})\s*(?:years?|yrs?)?', t, re.I)
        if age_m:
            age = int(age_m.group(1))
            if 0 < age < 120:
                result['patient_info']['age'] = age

        gender_m = re.search(r'(?:gender|sex)\s*[:\-]?\s*(male|female|m\b|f\b)', t, re.I)
        if gender_m:
            g = gender_m.group(1).lower()
            result['patient_info']['gender'] = 'Male' if g.startswith('m') else 'Female'

        phone_m = re.search(r'(?:phone|contact|tel)\s*[:\-]?\s*([\+\d][\d\s\-\(\)]{6,18})', t, re.I)
        if phone_m:
            result['patient_info']['contact'] = phone_m.group(1).strip()

        bg_m = re.search(r'(?:blood\s*group|blood\s*type)\s*[:\-]?\s*([ABO]{1,2}[+-])', t, re.I)
        if bg_m:
            result['patient_info']['blood_group'] = bg_m.group(1).strip()

        # ── Lab results — parse tabular data ─────────────────────────────────
        # Pattern: test name followed by numeric value, unit, reference range
        lab_pattern = re.compile(
            r'([A-Z][A-Z0-9\s\(\),\-\.]{3,60}?)'          # test name
            r'\s{2,}'                                        # 2+ spaces (column sep)
            r'([\d\.]+(?:\s*[\-\/]\s*[\d\.]+)?)'           # value (may be range)
            r'\s+'
            r'([a-zA-Z/%µ]+(?:/[a-zA-Z]+)?)'               # unit
            r'\s+'
            r'([\d\.]+\s*[\-–]\s*[\d\.]+)',                 # reference range
            re.M
        )
        seen_tests = set()
        for m in lab_pattern.finditer(t):
            test_name = m.group(1).strip().rstrip(':').strip()
            value = m.group(2).strip()
            unit = m.group(3).strip()
            ref = m.group(4).strip()
            if test_name.lower() in seen_tests or len(test_name) < 3:
                continue
            seen_tests.add(test_name.lower())
            # Determine if abnormal
            is_abnormal = False
            try:
                val_f = float(re.sub(r'[^\d.]', '', value.split('-')[0]))
                parts = re.split(r'[\-–]', ref)
                if len(parts) == 2:
                    lo, hi = float(parts[0].strip()), float(parts[1].strip())
                    is_abnormal = val_f < lo or val_f > hi
            except Exception:
                pass
            result['lab_results'].append({
                'test_name': test_name,
                'value': value,
                'unit': unit,
                'reference_range': ref,
                'is_abnormal': is_abnormal,
                'abnormality_type': 'OUT_OF_RANGE' if is_abnormal else '',
            })

        # ── Diagnoses — only from explicit section ────────────────────────────
        diag_m = re.search(
            r'(?:^|\n)(?:final\s+)?(?:diagnosis|diagnoses|impression|assessment)\s*[:\-]\s*'
            r'([^\n]{5,200}(?:\n(?!(?:symptoms?|medications?|history|plan|vitals?))[^\n]{3,200}){0,5})',
            t, re.I | re.M
        )
        if diag_m:
            raw = diag_m.group(1)
            diags = [d.strip() for d in re.split(r'[,;\n]', raw)
                     if _is_valid_medical_text(d, 5) and len(d.strip()) < 120]
            result['diagnoses'] = diags[:8]

        # ── Symptoms — only from explicit section ─────────────────────────────
        symp_m = re.search(
            r'(?:^|\n)(?:chief\s+)?(?:symptoms?|complaints?|presenting\s+complaints?)\s*[:\-]\s*'
            r'([^\n]{3,200}(?:\n(?!(?:diagnosis|medications?|history|plan|vitals?))[^\n]{3,200}){0,5})',
            t, re.I | re.M
        )
        if symp_m:
            raw = symp_m.group(1)
            symptoms = [s.strip() for s in re.split(r'[,;\n]', raw)
                        if _is_valid_medical_text(s, 3) and len(s.strip()) < 100]
            result['symptoms'] = symptoms[:8]

        # ── ICD-10 codes ──────────────────────────────────────────────────────
        icd_codes = re.findall(r'\b([A-Z]\d{2}(?:\.\d{1,4})?)\b', t)
        result['icd10_codes'] = list(set(icd_codes))[:10]

        # ── Vital signs ───────────────────────────────────────────────────────
        bp_m = re.search(r'(?:bp|blood\s*pressure)\s*[:\-]?\s*(\d{2,3}/\d{2,3})', t, re.I)
        if bp_m:
            result['vital_signs']['blood_pressure'] = bp_m.group(1)

        hr_m = re.search(r'(?:hr|heart\s*rate|pulse)\s*[:\-]?\s*(\d{2,3})\s*(?:bpm)?', t, re.I)
        if hr_m:
            result['vital_signs']['heart_rate'] = int(hr_m.group(1))

        temp_m = re.search(r'(?:temp(?:erature)?)\s*[:\-]?\s*(\d{2,3}(?:\.\d)?)\s*(?:°?[CF])?', t, re.I)
        if temp_m:
            result['vital_signs']['temperature'] = float(temp_m.group(1))

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

        # ── Medications ───────────────────────────────────────────────────────
        med_m = re.search(
            r'(?:^|\n)(?:medications?|drugs?|prescriptions?)\s*[:\-]\s*'
            r'([^\n]{3,}(?:\n(?!(?:diagnosis|symptoms?|history|plan|vitals?))[^\n]{3,}){0,9})',
            t, re.I | re.M
        )
        if med_m:
            for line in med_m.group(1).split('\n')[:10]:
                line = line.strip()
                if not _is_valid_medical_text(line, 3):
                    continue
                parts = re.split(r'\s{2,}', line, maxsplit=3)
                result['current_medications'].append({
                    "name": parts[0], "dosage": parts[1] if len(parts) > 1 else "",
                    "frequency": parts[2] if len(parts) > 2 else "",
                    "duration": "", "route": "",
                    "instructions": parts[3] if len(parts) > 3 else "",
                })

        # ── Medical history ───────────────────────────────────────────────────
        hist_m = re.search(
            r'(?:^|\n)(?:medical\s*history|past\s*history|pmh)\s*[:\-]\s*'
            r'([^\n]{3,}(?:\n(?!(?:diagnosis|symptoms?|medications?|plan))[^\n]{3,}){0,5})',
            t, re.I | re.M
        )
        if hist_m:
            history = [h.strip() for h in re.split(r'[,;\n]', hist_m.group(1))
                       if _is_valid_medical_text(h, 4)]
            result['medical_history'] = history[:8]

        # ── Abnormal findings — only from lab results, not raw text ───────────
        result['abnormal_findings'] = [
            r['test_name'] for r in result['lab_results'] if r['is_abnormal']
        ]

        # ── Severity ──────────────────────────────────────────────────────────
        critical_labs = sum(1 for r in result['lab_results'] if r['is_abnormal'])
        if re.search(r'\b(critical|emergency|severe|life.threatening)\b', t, re.I) or critical_labs >= 3:
            result['severity_level'] = 'CRITICAL'
        elif re.search(r'\b(high|significant|serious)\b', t, re.I) or critical_labs >= 1:
            result['severity_level'] = 'HIGH'
        elif re.search(r'\b(moderate|mild.to.moderate)\b', t, re.I):
            result['severity_level'] = 'MEDIUM'
        else:
            result['severity_level'] = 'LOW'

        # ── Summary ───────────────────────────────────────────────────────────
        summary_m = re.search(
            r'(?:^|\n)(?:summary|conclusion|impression|plan)\s*[:\-]\s*([^\n]{10,})',
            t, re.I | re.M
        )
        if summary_m:
            result['summary'] = summary_m.group(1).strip()[:500]
        else:
            lab_count = len(result['lab_results'])
            diag_count = len(result['diagnoses'])
            result['summary'] = (
                f"Report analyzed. Found {diag_count} diagnosis/diagnoses "
                f"and {lab_count} lab test(s)."
            )

        if result['severity_level'] in ('HIGH', 'CRITICAL'):
            result['clinical_suggestions'].append({
                "category": "Urgent Care",
                "suggestion": "Immediate medical attention recommended based on findings.",
                "confidence": 0.8,
                "priority": "HIGH",
                "reasoning": f"Severity level: {result['severity_level']}, "
                             f"abnormal labs: {len(result['abnormal_findings'])}",
            })

        return result
