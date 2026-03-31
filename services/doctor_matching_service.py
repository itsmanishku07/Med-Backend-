import logging

logger = logging.getLogger(__name__)

SPECIALTY_KEYWORDS = {
    'Cardiology': ['heart', 'cardiac', 'coronary', 'arrhythmia', 'myocardial', 'angina', 'hypertension'],
    'Neurology': ['brain', 'neuro', 'stroke', 'seizure', 'epilepsy', 'migraine', 'parkinson', 'alzheimer'],
    'Pulmonology': ['lung', 'pulmonary', 'asthma', 'copd', 'pneumonia', 'respiratory', 'bronchitis'],
    'Orthopedics': ['bone', 'joint', 'ortho', 'fracture', 'arthritis', 'spine', 'ligament', 'tendon'],
    'Dermatology': ['skin', 'derma', 'rash', 'eczema', 'psoriasis', 'melanoma', 'acne'],
    'Endocrinology': ['diabetes', 'thyroid', 'endo', 'insulin', 'hormone', 'adrenal', 'pituitary'],
    'Nephrology': ['kidney', 'renal', 'nephro', 'dialysis', 'creatinine', 'glomerulo'],
    'Gastroenterology': ['stomach', 'gastro', 'liver', 'intestine', 'colon', 'hepatitis', 'cirrhosis', 'ibs'],
    'Ophthalmology': ['eye', 'ophthal', 'vision', 'retina', 'glaucoma', 'cataract'],
}


class DoctorMatchingService:

    def detect_medical_specialty(self, ai_analysis: dict) -> str:
        """Map diagnoses/symptoms to a medical specialty."""
        text_sources = []
        text_sources.extend(ai_analysis.get('diagnoses', []))
        text_sources.extend(ai_analysis.get('symptoms', []))
        text_sources.extend(ai_analysis.get('abnormal_findings', []))
        summary = ai_analysis.get('summary', '')
        if summary:
            text_sources.append(summary)

        combined = ' '.join(str(s) for s in text_sources).lower()

        scores = {}
        for specialty, keywords in SPECIALTY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in combined)
            if score > 0:
                scores[specialty] = score

        if scores:
            return max(scores, key=scores.get)
        return 'General Medicine'

    def match_doctors_to_report(self, ai_analysis: dict, specialty: str,
                                doctors: list) -> list:
        """Score doctors by specialization match. Return top 5."""
        results = []
        specialty_lower = specialty.lower()

        for doctor in doctors:
            specializations = doctor.get('specializations') or []
            spec_lower = [s.lower() for s in specializations]

            score = 0.0
            # Exact specialty match
            if specialty_lower in spec_lower:
                score = 1.0
            else:
                # Partial keyword match
                for s in spec_lower:
                    if specialty_lower in s or s in specialty_lower:
                        score = 0.7
                        break
                    # Check keyword overlap
                    keywords = SPECIALTY_KEYWORDS.get(specialty, [])
                    if any(kw in s for kw in keywords):
                        score = max(score, 0.5)

            results.append({
                'doctor_id': doctor.get('firebase_uid') or doctor.get('id'),
                'doctor_name': doctor.get('name', ''),
                'match_score': score,
                'specializations': specializations,
            })

        results.sort(key=lambda x: x['match_score'], reverse=True)
        return results[:5]
