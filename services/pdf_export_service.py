import io
import re
from fpdf import FPDF
from datetime import datetime

class MedicalPDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.font_family_name = "Helvetica"

    def footer(self):
        # Position at 30 mm from bottom
        self.set_y(-30)
        self.set_font(self.font_family_name, "B", 8)
        self.set_text_color(180, 0, 0) # Red
        self.cell(0, 5, "CONFIDENTIAL MEDICAL ANALYSIS - FOR INFORMATIONAL PURPOSES ONLY", ln=True, align="C")
        
        self.set_font(self.font_family_name, "", 7)
        self.set_text_color(100, 100, 100) # Gray
        disclaimer = ("This report is an AI-assisted analysis and must NOT be used as a standalone diagnosis. "
                     "Any treatment changes must be discussed with a certified physician. MedReport AI is not liable "
                     "for decisions made based solely on this automated summary.")
        self.multi_cell(0, 4, disclaimer, align="C")
        
        # Page number
        self.set_y(-10)
        self.set_font(self.font_family_name, "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, "C")

class PDFExportService:
    def __init__(self):
        self.font_family = "Helvetica"
        self.primary_blue = (26, 115, 232)
        self.secondary_gray = (128, 128, 128)
        self.light_bg = (245, 247, 250)
        
    def generate_report_pdf(self, report_data, patient_name):
        # Using custom class with footer integration
        pdf = MedicalPDF()
        pdf.add_page()
        # Set bottom margin to 35mm to reserve space for footer
        pdf.set_auto_page_break(auto=True, margin=35)
        
        # --- Header ---
        pdf.set_font(self.font_family, "B", 22)
        pdf.set_text_color(*self.primary_blue)
        pdf.cell(0, 15, "MedReport AI - Clinical Analysis", ln=True, align="L")
        
        # Horizontal Line
        pdf.set_draw_color(*self.primary_blue)
        pdf.set_line_width(0.5)
        pdf.line(10, 25, 200, 25)
        
        pdf.ln(5)
        pdf.set_font(self.font_family, "", 9)
        pdf.set_text_color(*self.secondary_gray)
        pdf.cell(100, 6, f"Report ID: {report_data['id']}", ln=0)
        pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=1, align="R")
        pdf.ln(5)
        
        # --- Patient Information Section ---
        ai_analysis = report_data.get("ai_analysis", {})
        patient_info = ai_analysis.get("patient_info", {})
        
        pdf.set_fill_color(*self.light_bg)
        pdf.set_font(self.font_family, "B", 12)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, " PATIENT DETAILS", ln=True, fill=True)
        pdf.ln(3)
        
        def safe_get(val):
            if val is None or str(val).lower() == 'none' or str(val).strip() == '':
                return "Not specified"
            return str(val)

        pdf.set_font(self.font_family, "", 10)
        pdf.cell(30, 7, "Name:", 0)
        pdf.set_font(self.font_family, "B", 10)
        pdf.cell(65, 7, safe_get(patient_name), 0)
        
        pdf.set_font(self.font_family, "", 10)
        pdf.cell(30, 7, "Report Date:", 0)
        pdf.set_font(self.font_family, "B", 10)
        pdf.cell(0, 7, safe_get(report_data.get('uploaded_at', ''))[:10], ln=1)
        
        pdf.set_font(self.font_family, "", 10)
        pdf.cell(30, 7, "Age / Gender:", 0)
        pdf.set_font(self.font_family, "B", 10)
        age = safe_get(patient_info.get('age'))
        gender = safe_get(patient_info.get('gender'))
        pdf.cell(65, 7, f"{age} / {gender}", 0)
        
        pdf.set_font(self.font_family, "", 10)
        pdf.cell(30, 7, "Blood Group:", 0)
        pdf.set_font(self.font_family, "B", 10)
        pdf.cell(0, 7, safe_get(patient_info.get('blood_group')), ln=1)
        
        pdf.ln(8)
        
        # --- Analysis Summary & Findings ---
        pdf.set_fill_color(*self.light_bg)
        pdf.set_font(self.font_family, "B", 12)
        pdf.cell(0, 10, " ANALYSIS SUMMARY & FINDINGS", ln=True, fill=True)
        pdf.ln(5)
        
        summary = ai_analysis.get("summary", "")
        if summary:
            self._write_markdown_content(pdf, summary)
        else:
            pdf.set_font(self.font_family, "I", 10)
            pdf.cell(0, 10, "No summary available for this report.", ln=True)
        
        # --- Tables & Structured Sections ---
        # (The rest of the tables use the reserved bottom margin correctly now)
        
        vitals = ai_analysis.get("vital_signs", {})
        has_vitals = any(v and str(v).lower() != 'none' for v in vitals.values()) if vitals else False
        if has_vitals:
            pdf.ln(5)
            pdf.set_fill_color(*self.light_bg)
            pdf.set_font(self.font_family, "B", 12)
            pdf.cell(0, 10, " EXTRACTED VITAL SIGNS", ln=True, fill=True)
            pdf.ln(4)
            pdf.set_font(self.font_family, "B", 10)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(95, 8, "Biometric Metric", 1, 0, "C", fill=True)
            pdf.cell(95, 8, "Extracted Value", 1, 1, "C", fill=True)
            pdf.set_font(self.font_family, "", 10)
            for key, val in vitals.items():
                if val and str(val).lower() != 'none':
                    label = key.replace('_', ' ').capitalize()
                    pdf.cell(95, 8, label, 1, 0, "L")
                    pdf.cell(95, 8, str(val), 1, 1, "C")

        labs = ai_analysis.get("lab_results", [])
        if labs:
            pdf.ln(10)
            pdf.set_fill_color(*self.light_bg)
            pdf.set_font(self.font_family, "B", 12)
            pdf.cell(0, 10, " LABORATORY INVESTIGATIONS", ln=True, fill=True)
            pdf.ln(4)
            pdf.set_font(self.font_family, "B", 9)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(75, 8, "Test Description", 1, 0, "C", fill=True)
            pdf.cell(40, 8, "Result", 1, 0, "C", fill=True)
            pdf.cell(40, 8, "Ref. Range", 1, 0, "C", fill=True)
            pdf.cell(35, 8, "Interpretation", 1, 1, "C", fill=True)
            pdf.set_font(self.font_family, "", 9)
            for lab in labs:
                test_name = safe_get(lab.get('test_name') or lab.get('name'))
                result = f"{safe_get(lab.get('value'))} {safe_get(lab.get('unit'))}"
                ref = safe_get(lab.get('reference_range'))
                is_abnormal = lab.get('is_abnormal')
                status = "Abnormal" if is_abnormal else "Normal"
                pdf.cell(75, 8, test_name[:40], 1, 0, "L")
                pdf.cell(40, 8, result, 1, 0, "C")
                pdf.cell(40, 8, ref[:20], 1, 0, "C")
                if is_abnormal:
                    pdf.set_text_color(200, 0, 0)
                    pdf.set_font(self.font_family, "B", 9)
                pdf.cell(35, 8, status, 1, 1, "C")
                pdf.set_text_color(0, 0, 0)
                pdf.set_font(self.font_family, "", 9)

        self._add_formatted_section(pdf, "PRESCRIBED MEDICATIONS", ai_analysis.get("current_medications", []))
        self._add_formatted_section(pdf, "CLINICAL RECOMMENDATIONS", ai_analysis.get("clinical_suggestions", []))

        if report_data.get('doctor_notes'):
            pdf.ln(5)
            pdf.set_fill_color(*self.light_bg)
            pdf.set_font(self.font_family, "B", 12)
            pdf.cell(0, 10, " MEDICAL REVIEWER COMMENTS", ln=True, fill=True)
            pdf.ln(3)
            pdf.set_font(self.font_family, "I", 10)
            pdf.multi_cell(0, 6, report_data['doctor_notes'])
        
        return pdf.output()

    def _write_markdown_content(self, pdf, text):
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                pdf.ln(2)
                continue
            if line.startswith('###'):
                pdf.ln(2)
                pdf.set_font(self.font_family, "B", 11)
                pdf.set_text_color(*self.primary_blue)
                pdf.cell(0, 8, line.replace('###', '').strip(), ln=1)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font(self.font_family, "", 10)
                continue
            is_bullet = False
            if line.startswith('* ') or line.startswith('- '):
                is_bullet = True
                line = line[2:].strip()
                pdf.set_x(15)
                pdf.cell(5, 6, chr(149), 0, 0)

            parts = re.split(r'(\*\*.*?\*\*)', line)
            for part in parts:
                if part.startswith('**') and part.endswith('**'):
                    pdf.set_font(self.font_family, "B", 10)
                    content = part.replace('**', '')
                    pdf.write(6, content)
                else:
                    pdf.set_font(self.font_family, "", 10)
                    pdf.write(6, part)
            pdf.ln(6 if not is_bullet else 7)

    def _add_formatted_section(self, pdf, title, items):
        if not items: return
        pdf.ln(10)
        pdf.set_fill_color(*self.light_bg)
        pdf.set_font(self.font_family, "B", 12)
        pdf.cell(0, 10, f" {title}", ln=True, fill=True)
        pdf.ln(3)
        pdf.set_font(self.font_family, "", 10)
        for item in items:
            if isinstance(item, dict):
                name = item.get('name') or item.get('medication') or item.get('suggestion') or ""
                dosage = item.get('dosage') or item.get('frequency') or ""
                instr = item.get('instructions') or ""
                text = f"**{name}**"
                if dosage: text += f" - {dosage}"
                if instr: text += f" ({instr})"
            else: text = str(item)
            if text: self._write_markdown_content(pdf, "* " + text)
