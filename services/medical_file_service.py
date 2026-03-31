import io
import re
import logging

logger = logging.getLogger(__name__)


class MedicalFileService:

    def extract_text(self, file_content: bytes, file_type: str) -> str:
        """Extract text from PDF or image. Never raises — returns empty string on failure."""
        try:
            ft = file_type.lower().lstrip('.')
            if ft == 'pdf':
                return self._extract_pdf(file_content)
            elif ft in ('jpg', 'jpeg', 'png'):
                return self._extract_image(file_content)
            else:
                return ''
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return ''

    def _extract_pdf(self, content: bytes) -> str:
        text = ''
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                parts = []
                for page in pdf.pages:
                    page_text = page.extract_text() or ''
                    page_text = self._decode_unicode_private(page_text)
                    parts.append(page_text)
                    # Extract tables
                    tables = page.extract_tables() or []
                    for table in tables:
                        for row in table:
                            if row:
                                parts.append(' | '.join(str(c) for c in row if c))
                text = '\n'.join(parts)
        except Exception as e:
            logger.warning(f"pdfplumber failed: {e}, trying PyPDF2")
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(io.BytesIO(content))
                parts = []
                for page in reader.pages:
                    t = page.extract_text() or ''
                    parts.append(self._decode_unicode_private(t))
                text = '\n'.join(parts)
            except Exception as e2:
                logger.error(f"PyPDF2 also failed: {e2}")
        return text

    def _decode_unicode_private(self, text: str) -> str:
        """Map Unicode private-use area U+F000–U+F0FF to ASCII."""
        result = []
        for ch in text:
            cp = ord(ch)
            if 0xF000 <= cp <= 0xF0FF:
                result.append(chr(cp - 0xF000))
            else:
                result.append(ch)
        return ''.join(result)

    def _extract_image(self, content: bytes) -> str:
        """Try easyocr first, fall back to pytesseract."""
        img_array = self._preprocess_image(content)
        if img_array is None:
            return ''

        # easyocr primary
        try:
            import easyocr
            reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            results = reader.readtext(img_array, detail=0)
            text = ' '.join(results)
            if text.strip():
                return text
        except Exception as e:
            logger.warning(f"easyocr failed: {e}")

        # pytesseract fallback
        try:
            import pytesseract
            from PIL import Image
            pil_img = Image.fromarray(img_array)
            text = pytesseract.image_to_string(pil_img)
            return text
        except Exception as e:
            logger.error(f"pytesseract failed: {e}")
            return ''

    def _preprocess_image(self, content: bytes):
        """Convert to RGB numpy array, enhance contrast, resize if small."""
        try:
            import numpy as np
            import cv2
            from PIL import Image, ImageEnhance

            pil_img = Image.open(io.BytesIO(content)).convert('RGB')

            # Enhance contrast
            enhancer = ImageEnhance.Contrast(pil_img)
            pil_img = enhancer.enhance(1.5)

            # Resize if too small
            w, h = pil_img.size
            if w < 800 or h < 800:
                scale = max(800 / w, 800 / h)
                pil_img = pil_img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

            return np.array(pil_img)
        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            return None
