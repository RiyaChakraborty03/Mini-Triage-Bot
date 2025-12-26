import google.generativeai as genai
import os
from PIL import Image

# 1. Setup the AI (Paste your key here)
YOUR_API_KEY = "AIzaSy..." # Replace with your real key
genai.configure(api_key=YOUR_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# 2. Path to your files
LOG_PATH = "logs/fail_log.txt"
IMAGE_PATH = "logs/failure.png"

def analyze_nightly_failure():
    print("--- 🔍 Analyzing Nightly Regression Failures ---")

    # A. READ THE TEXT LOG
    with open(LOG_PATH, "r") as f:
        error_text = f.read()

    # B. ANALYZE WITH AI (Text only)
    print("\n[1/2] Asking AI about the error log...")
    text_response = model.generate_content(
        f"You are a Senior QA Engineer. Analyze this error log and explain in 2 simple sentences: "
        f"1. What failed? 2. Is it a code bug or a timing issue?\n\nError: {error_text}"
    )
    print(f"AI SUMMARY: {text_response.text}")

    # C. ANALYZE WITH AI (Visual - Stretch Goal!)
    print("\n[2/2] Asking AI about the screenshot...")
    sample_file = Image.open(IMAGE_PATH)
    img_response = model.generate_content(
        ["Look at this UI failure screenshot. Tell me what visual element looks broken or missing.", sample_file]
    )
    print(f"AI VISUAL ANALYSIS: {img_response.text}")

if __name__ == "__main__":
    analyze_nightly_failure()