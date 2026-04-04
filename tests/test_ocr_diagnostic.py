import shutil
import subprocess
import sys
import os

def check_tesseract():
    print("--- Tesseract OCR Diagnosis ---")
    path = shutil.which("tesseract")
    if path:
        print(f"[OK] Tesseract binary found at: {path}")
        try:
            version = subprocess.check_output(["tesseract", "--version"], stderr=subprocess.STDOUT).decode()
            print(f"[INFO] Tesseract Version: {version.splitlines()[0]}")
        except Exception as e:
            print(f"[ERROR] Found tesseract but could not run it: {e}")
    else:
        print("[FAIL] Tesseract binary NOT found in PATH.")
        print("      Action: Run 'sudo apt-get install tesseract-ocr' (Ubuntu) or 'sudo yum install tesseract' (Amazon Linux)")

def check_python_deps():
    print("\n--- Python Dependencies ---")
    try:
        from PIL import Image
        print("[OK] Pillow is installed.")
    except ImportError:
        print("[FAIL] Pillow is NOT installed.")
        
    try:
        import pytesseract
        print("[OK] pytesseract is installed.")
    except ImportError:
        print("[FAIL] pytesseract is NOT installed.")

def check_env_vars():
    print("\n--- Environment Variables ---")
    from dotenv import load_dotenv
    load_dotenv()
    
    model = os.getenv('DATABRICKS_MODEL_ENDPOINT', 'Not Set')
    vision_model = os.getenv('DATABRICKS_VISION_MODEL_ENDPOINT', 'Not Set')
    
    print(f"DATABRICKS_MODEL_ENDPOINT: {model}")
    print(f"DATABRICKS_VISION_MODEL_ENDPOINT: {vision_model}")
    
    if vision_model == model and "llama-3-1" in model:
        print("[WARNING] Vision model is the same as text model (Llama 3.1). Image analysis might fail.")
        print("          Recommendation: Set DATABRICKS_VISION_MODEL_ENDPOINT to a vision-capable model.")

if __name__ == "__main__":
    check_tesseract()
    check_python_deps()
    check_env_vars()
