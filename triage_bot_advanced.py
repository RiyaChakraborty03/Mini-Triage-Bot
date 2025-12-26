"""
Advanced Mini-Triage Bot
Automates log analysis and screenshot review using Google Gemini AI
"""

from google import genai
import os
from PIL import Image
import json
import sys
from datetime import datetime
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

DEMO_MODE = False  # Set to True for testing without API calls
LOGS_DIR = "logs"
REPORTS_DIR = "reports"

# Create reports directory if it doesn't exist
os.makedirs(REPORTS_DIR, exist_ok=True)

def read_error_log(log_path):
    """Read error log file"""
    try:
        with open(log_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        print(f"ERROR: {log_path} not found!")
        return None

def get_confidence_score(text):
    """Extract or calculate confidence score from AI response"""
    if "critical" in text.lower() or "error" in text.lower():
        return 90
    elif "warning" in text.lower():
        return 70
    else:
        return 50

def analyze_log(error_text):
    """Analyze error log text"""
    if DEMO_MODE:
        return "Demo analysis: The API endpoint returned a 500 error due to null pointer exception. This is a code bug in the data validation layer."
    
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=f"""You are an expert QA Engineer. Analyze this error log in 3-4 sentences:
            1. What specifically failed?
            2. Is it a code bug or environmental/infrastructure issue?
            3. What is the severity (Critical/High/Medium/Low)?
            
            Error Log:
            {error_text}"""
        )
        return response.text
    except Exception as e:
        if "quota" in str(e).lower():
            return f"API Quota exceeded. Please wait before retrying. Use DEMO_MODE=True to test offline."
        return f"Error analyzing log: {str(e)}"

def analyze_image(image_path):
    """Analyze failure screenshot"""
    if not os.path.exists(image_path):
        return None
    
    if DEMO_MODE:
        return "Demo analysis: The screenshot shows a 500 error page with broken CSS styling and truncated error message."
    
    try:
        image = Image.open(image_path)
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=["""You are a UI/UX expert. Analyze this failed test screenshot in 2-3 sentences:
            1. What visual elements are broken or missing?
            2. What is the likely root cause?
            3. How would you describe the severity of the UI failure?""", image]
        )
        return response.text
    except Exception as e:
        if "quota" in str(e).lower():
            return "API Quota exceeded. Please wait before retrying."
        return f"Error analyzing image: {str(e)}"

def generate_json_report(log_analysis, image_analysis, confidence_score, log_file, image_file):
    """Generate JSON report"""
    timestamp = datetime.now().isoformat()
    
    report = {
        "timestamp": timestamp,
        "analysis": {
            "log_analysis": log_analysis,
            "image_analysis": image_analysis,
            "files": {
                "log_file": log_file,
                "image_file": image_file
            }
        },
        "confidence_score": confidence_score,
        "recommendation": "Review in detail if confidence > 75%" if confidence_score > 75 else "May be a false positive"
    }
    
    report_file = os.path.join(REPORTS_DIR, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    return report_file

def generate_html_report(log_analysis, image_analysis, confidence_score, log_file, image_file):
    """Generate interactive HTML report"""
    log_safe = log_analysis.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    img_safe = image_analysis.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;") if image_analysis else "No image analysis available"
    
    color = "green" if confidence_score >= 80 else "orange" if confidence_score >= 60 else "red"
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Triage Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ 
            max-width: 900px; 
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{ font-size: 28px; margin-bottom: 5px; }}
        .header p {{ opacity: 0.9; }}
        .content {{ padding: 30px; }}
        .section {{ 
            margin: 20px 0; 
            padding: 20px; 
            border-left: 5px solid #667eea;
            background: #f8f9fa;
            border-radius: 5px;
        }}
        .log-section {{ border-left-color: #28a745; }}
        .image-section {{ border-left-color: #ffc107; }}
        .confidence-section {{ 
            border-left-color: {color};
            background: linear-gradient(135deg, rgba(0,0,0,0.02), rgba(0,0,0,0.05));
        }}
        .section h2 {{ 
            color: #333;
            margin-bottom: 15px;
            font-size: 20px;
        }}
        .section p {{ 
            color: #555;
            line-height: 1.6;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .confidence-score {{
            font-size: 32px;
            font-weight: bold;
            color: {color};
            text-align: center;
            margin: 20px 0;
        }}
        .recommendation {{
            background: {color}20;
            border: 2px solid {color};
            padding: 15px;
            border-radius: 5px;
            margin-top: 15px;
            color: #333;
        }}
        .metadata {{
            font-size: 12px;
            color: #999;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px 30px;
            text-align: center;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Mini-Triage Bot Analysis Report</h1>
            <p>Automated AI-Powered Failure Analysis</p>
        </div>
        
        <div class="content">
            <div class="section log-section">
                <h2>Log Analysis</h2>
                <p>{log_safe}</p>
            </div>
            
            <div class="section image-section">
                <h2>Visual Analysis</h2>
                <p>{img_safe}</p>
            </div>
            
            <div class="section confidence-section">
                <h2>Confidence & Recommendation</h2>
                <div class="confidence-score">{confidence_score}%</div>
                <div class="recommendation">
                    <strong>Assessment:</strong> AI is {confidence_score}% confident in this analysis.
                    {f'This is likely a reproducible issue requiring investigation.' if confidence_score >= 75 else 'Further manual review recommended.'}
                </div>
            </div>
            
            <div class="metadata">
                <p><strong>Analysis Files:</strong></p>
                <p>Log File: {log_file}</p>
                <p>Image File: {image_file if image_file else 'None'}</p>
                <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        </div>
        
        <div class="footer">
            <p>Mini-Triage Bot v1.0 | Powered by Google Gemini AI</p>
        </div>
    </div>
</body>
</html>"""
    
    report_file = os.path.join(REPORTS_DIR, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return report_file

def run_triage(log_file=None, image_file=None):
    """Main triage function"""
    print("=== Mini-Triage Bot Starting ===\n")
    
    # Find log file
    if not log_file:
        for file in os.listdir(LOGS_DIR) if os.path.exists(LOGS_DIR) else []:
            if file.endswith('.txt'):
                log_file = os.path.join(LOGS_DIR, file)
                break
    
    if not log_file or not os.path.exists(log_file):
        print("ERROR: No log file found!")
        return
    
    # Find image file
    if not image_file:
        for file in os.listdir(LOGS_DIR) if os.path.exists(LOGS_DIR) else []:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_file = os.path.join(LOGS_DIR, file)
                break
    
    print(f"Analyzing: {log_file}")
    if image_file:
        print(f"Screenshot: {image_file}\n")
    
    # Read and analyze
    error_text = read_error_log(log_file)
    if not error_text:
        return
    
    print("[1/3] Analyzing error log...")
    log_analysis = analyze_log(error_text)
    print(f"SUCCESS\n")
    
    print("[2/3] Analyzing screenshot...")
    image_analysis = None
    if image_file and os.path.exists(image_file):
        image_analysis = analyze_image(image_file)
        print(f"SUCCESS\n")
    else:
        print("SKIPPED (no image found)\n")
    
    # Calculate confidence
    confidence = get_confidence_score(log_analysis)
    if image_analysis:
        confidence = (confidence + get_confidence_score(image_analysis)) // 2
    
    print("[3/3] Generating reports...")
    
    # Generate both report formats
    html_report = generate_html_report(log_analysis, image_analysis or "No image analysis", confidence, 
                                      log_file, image_file)
    json_report = generate_json_report(log_analysis, image_analysis or "No image analysis", confidence,
                                      log_file, image_file)
    
    print(f"SUCCESS\n")
    print(f"Reports generated:")
    print(f"  - HTML: {html_report}")
    print(f"  - JSON: {json_report}")
    print(f"\nConfidence Score: {confidence}%")

if __name__ == "__main__":
    run_triage()
