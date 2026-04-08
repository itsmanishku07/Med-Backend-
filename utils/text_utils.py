import re

def clean_medical_text(text: str) -> str:
    """
    Cleans raw text extracted from medical reports.
    Based on the ResumeBot-Assignment cleaning logic:
    - Normalizes white-space and line breaks.
    - Removes non-printable characters.
    - Preserves key medical formatting (like units and lab labels).
    """
    if not text:
        return ""

    text = re.sub(r'[\r\n]+', '\n', text)
    text = re.sub(r'[^\x20-\x7E\n]', '', text)

    text = re.sub(r' {3,}', '  ', text)

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    return '\n'.join(lines)
