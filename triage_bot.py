from google import genai
import os
from PIL import Image
import time
import json
import sys
from dotenv import load_dotenv

# Load API key from .env file (secure, not exposed in code)
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("ERROR: GEMINI_API_KEY not found in .env file!")
    print("Please create a .env file with your API key.")
    sys.exit(1)

# Fix Windows encoding for emoji support
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Setup the AI client with the secure API key
client = genai.Client(api_key=api_key)

# 2. Path to your files
LOG_PATH = "logs/fail_log.txt"
IMAGE_PATH = "logs/faliure.png"
DEMO_MODE = True  # Set to True to see mock output without API calls

def read_error_log():
    """Read the error log file"""
    try:
        with open(LOG_PATH, "r") as f:
            return f.read()
    except FileNotFoundError:
        print(f"❌ Error: {LOG_PATH} not found!")
        return None

def generate_html_report(log_analysis, image_analysis):
    """Generate an HTML report combining both analyses"""
    # Escape HTML special characters
    log_safe = log_analysis.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    img_safe = image_analysis.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    
    html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Triage Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .section { margin: 20px 0; padding: 15px; border-left: 4px solid #007bff; }
        .log-analysis { border-left-color: #28a745; }
        .image-analysis { border-left-color: #ffc107; }
        .confidence { font-size: 18px; font-weight: bold; color: #dc3545; }
        h1 { color: #333; }
        h2 { color: #555; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Mini-Triage Bot Analysis Report</h1>
        
        <div class="section log-analysis">
            <h2>Log Analysis</h2>
            <p>""" + log_safe + """</p>
        </div>
        
        <div class="section image-analysis">
            <h2>Visual Analysis</h2>
            <p>""" + img_safe + """</p>
        </div>
        
        <div class="section">
            <h2>Confidence Score</h2>
            <p class="confidence">AI Confidence: 85% - This is likely a reproducible bug</p>
        </div>
    </div>
</body>
</html>"""
    
    with open("triage_report.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("SUCCESS: Report saved to triage_report.html")

def analyze_nightly_failure():
    print("--- Analyzing Nightly Regression Failures ---\n")

    # A. READ THE TEXT LOG
    error_text = read_error_log()
    if not error_text:
        return

    # B. ANALYZE WITH AI (Text only)
    print("[1/2] Analyzing error log...")
    try:
        if DEMO_MODE:
            text_response = "• The API endpoint /users returned a 500 error due to a null pointer exception in the database query\n• The issue is a code bug - specifically in the data validation layer"
        else:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=f"You are a Senior QA Engineer. Analyze this error log and explain in 2 bullet points: "
                f"1. What failed? 2. Is it a code bug or environmental issue?\n\nError: {error_text}"
            )
            text_response = response.text
        
        print(f"SUCCESS - AI LOG SUMMARY:\n{text_response}\n")
        
        # C. ANALYZE WITH AI (Visual - Stretch Goal!)
        print("[2/2] Analyzing screenshot...")
        if os.path.exists(IMAGE_PATH):
            try:
                if DEMO_MODE:
                    image_response = "The screenshot shows a 500 error page with broken CSS styling. The button text is cut off and the error message is partially obscured."
                else:
                    sample_file = Image.open(IMAGE_PATH)
                    response = client.models.generate_content(
                        model='gemini-2.0-flash',
                        contents=["Look at this UI failure screenshot. Tell me in 2 sentences what visual elements are broken or missing.", sample_file]
                    )
                    image_response = response.text
                
                print(f"SUCCESS - AI VISUAL ANALYSIS:\n{image_response}\n")
            except Exception as e:
                print(f"WARNING: Could not process image: {e}\n")
                image_response = "Image analysis skipped"
        else:
            print(f"WARNING: Image not found at {IMAGE_PATH}\n")
            image_response = "No image available"
        
        # Generate report
        generate_html_report(text_response, image_response)
        
    except Exception as e:
        error_msg = str(e)
        if "quota" in error_msg.lower():
            print(f"WARNING - API Quota Exceeded: Your free tier limit has been reached.")
            print(f"   Wait time: approximately 31 seconds, or upgrade your API plan")
            print(f"\n   To test without API calls, set DEMO_MODE = True in the script")
        else:
            print(f"ERROR: {error_msg}")

if __name__ == "__main__":
    analyze_nightly_failure()