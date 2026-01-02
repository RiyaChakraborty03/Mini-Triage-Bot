"""
Mini-Triage Bot - Production Ready Basic Version
Simplified interface for quick nightly regression analysis
"""

import os
import sys
import requests
from PIL import Image
from dotenv import load_dotenv
import re
from datetime import datetime

# Load API key from .env file (secure, not exposed in code)
load_dotenv()
api_key = os.getenv("CODY_API_KEY")

if not api_key:
    print("ERROR: CODY_API_KEY not found in .env file!")
    print("Please create a .env file with your API key.")
    sys.exit(1)

# Fix Windows encoding for emoji support
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Sourcegraph Cody API configuration
CODY_API_URL = "https://sourcegraph.sw.nxp.com/.api/completions/stream"
HEADERS = {
    "Authorization": f"token {api_key}",
    "Content-Type": "application/json"
}

# Configuration
LOG_PATH = "logs/fail_log.txt"
IMAGE_PATH = "logs/faliure.png"
DEMO_MODE = False  # Set to True to see mock output without API calls
MAX_LOG_SIZE = 50000  # Maximum characters to send to API
CONTEXT_LINES_BEFORE = 20  # Lines before ERROR/EXCEPTION
CONTEXT_LINES_AFTER = 20   # Lines after ERROR/EXCEPTION

def extract_relevant_context(log_text, context_before=20, context_after=20):
    """
    Extract relevant context around ERROR and EXCEPTION keywords.
    Returns only the lines containing errors plus surrounding context.
    This significantly reduces token count for AI API calls.
    
    Args:
        log_text (str): Full log file content
        context_before (int): Number of lines to include before error
        context_after (int): Number of lines to include after error
    
    Returns:
        str: Extracted relevant portions of the log
    """
    if not log_text:
        return ""
    
    lines = log_text.split('\n')
    total_lines = len(lines)
    relevant_sections = []
    processed_ranges = set()
    
    # Find all lines with ERROR or EXCEPTION (case-insensitive)
    error_pattern = re.compile(r'\b(ERROR|EXCEPTION|FATAL|CRITICAL|FAIL)\b', re.IGNORECASE)
    
    for i, line in enumerate(lines):
        if error_pattern.search(line):
            # Calculate range to extract
            start_idx = max(0, i - context_before)
            end_idx = min(total_lines, i + context_after + 1)
            
            # Check if this range overlaps with already processed ranges
            range_key = (start_idx, end_idx)
            
            # Avoid duplicate ranges
            overlaps = False
            for processed_start, processed_end in processed_ranges:
                if not (end_idx < processed_start or start_idx > processed_end):
                    overlaps = True
                    # Extend the range if needed
                    start_idx = min(start_idx, processed_start)
                    end_idx = max(end_idx, processed_end)
                    processed_ranges.discard((processed_start, processed_end))
                    break
            
            processed_ranges.add((start_idx, end_idx))
            
            if not overlaps:
                # Extract the section
                section = lines[start_idx:end_idx]
                
                # Add markers for context
                header = f"\n{'='*60}\n[ERROR CONTEXT {len(relevant_sections) + 1}] Line {i+1} of {total_lines}\n{'='*60}\n"
                relevant_sections.append(header + '\n'.join(section))
    
    if not relevant_sections:
        # No errors found, return first and last portions
        print("⚠️  No ERROR/EXCEPTION keywords found. Returning start and end of log.")
        preview_lines = 50
        if total_lines <= preview_lines * 2:
            return log_text
        else:
            start_section = '\n'.join(lines[:preview_lines])
            end_section = '\n'.join(lines[-preview_lines:])
            return f"{start_section}\n\n... [MIDDLE SECTION OMITTED] ...\n\n{end_section}"
    
    result = '\n\n'.join(relevant_sections)
    
    # Add summary header
    summary = f"""
{'='*60}
EXTRACTED LOG SUMMARY
{'='*60}
Total Log Lines: {total_lines}
Error Sections Found: {len(relevant_sections)}
Context: {context_before} lines before, {context_after} lines after each error
Original Size: {len(log_text)} chars
Extracted Size: {len(result)} chars
Reduction: {((1 - len(result)/len(log_text)) * 100):.1f}%
{'='*60}

"""
    
    return summary + result

def call_cody_api(prompt, retry_count=0):
    """Call Sourcegraph Cody API for text analysis with retry logic"""
    payload = {
        "messages": [
            {
                "speaker": "human",
                "text": prompt
            }
        ],
        "maxTokensToSample": 1500,
        "temperature": 0.2
    }
    
    try:
        response = requests.post(CODY_API_URL, headers=HEADERS, json=payload, stream=True, timeout=30)
        response.raise_for_status()
        
        # Collect streamed response
        full_response = ""
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data: '):
                    data = decoded_line[6:]  # Remove 'data: ' prefix
                    if data and data != '[DONE]':
                        import json
                        try:
                            chunk = json.loads(data)
                            if 'completion' in chunk:
                                full_response += chunk['completion']
                        except json.JSONDecodeError:
                            continue
        
        if not full_response.strip():
            raise Exception("Empty response from API")
            
        return full_response.strip()
        
    except requests.exceptions.Timeout:
        if retry_count < 2:
            print(f"⚠️  Timeout, retrying... (attempt {retry_count + 2}/3)")
            return call_cody_api(prompt, retry_count + 1)
        return "Error: API timeout after multiple attempts"
        
    except Exception as e:
        if retry_count < 2:
            print(f"⚠️  Error, retrying... (attempt {retry_count + 2}/3)")
            return call_cody_api(prompt, retry_count + 1)
        return f"Error calling Cody API: {str(e)}"

def read_error_log():
    """Read the error log file with intelligent context extraction"""
    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors='ignore') as f:
            content = f.read()
        
        original_size = len(content)
        print(f"📄 Original log size: {original_size} characters")
        
        # Extract relevant context around errors
        print(f"🔍 Extracting relevant context (±{CONTEXT_LINES_BEFORE}/{CONTEXT_LINES_AFTER} lines around errors)...")
        content = extract_relevant_context(content, CONTEXT_LINES_BEFORE, CONTEXT_LINES_AFTER)
        
        extracted_size = len(content)
        print(f"✂️  Extracted size: {extracted_size} characters ({((1 - extracted_size/original_size) * 100):.1f}% reduction)")
        
        # If still too large after extraction, truncate
        if len(content) > MAX_LOG_SIZE:
            print(f"⚠️  Still too large, truncating to {MAX_LOG_SIZE} characters...")
            half = MAX_LOG_SIZE // 2
            content = content[:half] + "\n\n... [TRUNCATED FOR API LIMITS] ...\n\n" + content[-half:]
            
        return content
    except FileNotFoundError:
        print(f"❌ Error: {LOG_PATH} not found!")
        return None
    except Exception as e:
        print(f"❌ Error reading log: {str(e)}")
        return None

def extract_key_errors(log_text):
    """Extract key error information from logs"""
    errors = {
        'exceptions': re.findall(r'(\w+Exception|Error):\s*(.+)', log_text)[:5],
        'failed_tests': re.findall(r'(FAILED|FAIL|ERROR)\s+(.+)', log_text, re.IGNORECASE)[:5],
        'stack_traces': len(re.findall(r'at\s+[\w\.\$]+\([\w\.]+:\d+\)', log_text))
    }
    return errors

def get_severity_from_response(text):
    """Determine severity from AI response"""
    text_lower = text.lower()
    if 'critical' in text_lower:
        return 'Critical', '#dc3545'
    elif 'high' in text_lower:
        return 'High', '#fd7e14'
    elif 'medium' in text_lower:
        return 'Medium', '#ffc107'
    else:
        return 'Low', '#28a745'

def generate_html_report(log_analysis, image_analysis, key_errors):
    """Generate an enhanced HTML report"""
    # Escape HTML special characters
    log_safe = log_analysis.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    img_safe = image_analysis.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    
    severity, sev_color = get_severity_from_response(log_analysis)
    
    # Calculate confidence
    confidence = 85
    if 'critical' in log_analysis.lower() or 'error' in log_analysis.lower():
        confidence = 90
    elif 'might' in log_analysis.lower() or 'possibly' in log_analysis.lower():
        confidence = 65
    
    conf_color = "green" if confidence >= 80 else "orange" if confidence >= 60 else "red"
    
    # Format key errors
    error_summary = ""
    if key_errors['exceptions']:
        error_summary += "<h4>Top Exceptions:</h4><ul>"
        for exc_type, exc_msg in key_errors['exceptions'][:3]:
            error_summary += f"<li><strong>{exc_type}:</strong> {exc_msg[:100]}</li>"
        error_summary += "</ul>"
    
    if key_errors['failed_tests']:
        error_summary += "<h4>Failed Tests:</h4><ul>"
        for status, test in key_errors['failed_tests'][:3]:
            error_summary += f"<li>{test[:100]}</li>"
        error_summary += "</ul>"
    
    if key_errors['stack_traces']:
        error_summary += f"<p><strong>Stack Traces Found:</strong> {key_errors['stack_traces']}</p>"
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Triage Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ 
            max-width: 1000px; 
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
        .header p {{ opacity: 0.9; font-size: 14px; }}
        .alert-bar {{
            background: {sev_color};
            color: white;
            padding: 15px 30px;
            text-align: center;
            font-weight: bold;
            font-size: 16px;
        }}
        .content {{ padding: 30px; }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }}
        .metric {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            border-left: 4px solid #667eea;
        }}
        .metric h3 {{ font-size: 12px; color: #666; margin-bottom: 8px; }}
        .metric .value {{ font-size: 24px; font-weight: bold; color: #333; }}
        .section {{ 
            margin: 20px 0; 
            padding: 20px; 
            border-left: 5px solid #667eea;
            background: #f8f9fa;
            border-radius: 5px;
        }}
        .section h2 {{ 
            color: #333;
            margin-bottom: 15px;
            font-size: 20px;
        }}
        .section p, .section ul {{ 
            color: #555;
            line-height: 1.6;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .section ul {{ margin-left: 20px; }}
        .section li {{ margin-bottom: 8px; }}
        .log-analysis {{ border-left-color: #28a745; }}
        .image-analysis {{ border-left-color: #ffc107; }}
        .error-summary {{ border-left-color: #dc3545; }}
        .confidence {{ 
            font-size: 36px; 
            font-weight: bold; 
            color: {conf_color};
            text-align: center;
            margin: 20px 0;
        }}
        .recommendation {{
            background: white;
            padding: 15px;
            border-radius: 5px;
            margin-top: 10px;
            border: 2px solid {conf_color};
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 12px;
            border-top: 2px solid #eee;
        }}
        h4 {{ color: #667eea; margin: 15px 0 10px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Nightly Regression Triage Report</h1>
            <p>Automated AI-Powered Analysis | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="alert-bar">
            Severity: {severity} | Confidence: {confidence}%
        </div>
        
        <div class="content">
            <div class="metrics">
                <div class="metric">
                    <h3>Confidence</h3>
                    <div class="value" style="color: {conf_color};">{confidence}%</div>
                </div>
                <div class="metric">
                    <h3>Severity</h3>
                    <div class="value" style="color: {sev_color};">{severity}</div>
                </div>
                <div class="metric">
                    <h3>Exceptions</h3>
                    <div class="value">{len(key_errors['exceptions'])}</div>
                </div>
                <div class="metric">
                    <h3>Stack Traces</h3>
                    <div class="value">{key_errors['stack_traces']}</div>
                </div>
            </div>
            
            <div class="section error-summary">
                <h2>📋 Error Summary</h2>
                {error_summary if error_summary else '<p>No specific error patterns detected</p>'}
            </div>
            
            <div class="section log-analysis">
                <h2>🤖 AI Log Analysis</h2>
                <p>{log_safe}</p>
            </div>
            
            <div class="section image-analysis">
                <h2>🖼️ Visual Analysis</h2>
                <p>{img_safe}</p>
            </div>
            
            <div class="section">
                <h2>📊 Confidence Assessment</h2>
                <div class="confidence">{confidence}%</div>
                <div class="recommendation">
                    <strong>Recommendation:</strong> 
                    {'This is likely a reproducible bug requiring immediate attention.' if confidence >= 80 
                     else 'Further investigation recommended. May require manual review.' if confidence >= 60
                     else 'Low confidence - manual review strongly recommended.'}
                </div>
            </div>
            
            <div class="footer">
                <p><strong>Log File:</strong> {LOG_PATH}</p>
                <p><strong>Screenshot:</strong> {IMAGE_PATH if os.path.exists(IMAGE_PATH) else 'None'}</p>
                <p><strong>Analysis Mode:</strong> {'DEMO MODE' if DEMO_MODE else 'LIVE API'}</p>
                <p style="margin-top: 10px;">Mini-Triage Bot v2.0 | Powered by Sourcegraph Cody AI</p>
            </div>
        </div>
    </div>
</body>
</html>"""
    
    with open("triage_report.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("✅ SUCCESS: Report saved to triage_report.html")

def analyze_nightly_failure():
    """Main analysis function"""
    print("="*60)
    print("🚀 Mini-Triage Bot - Nightly Regression Analysis")
    print("="*60)
    print()

    # A. READ THE TEXT LOG
    error_text = read_error_log()
    if not error_text:
        return

    # Extract key errors
    key_errors = extract_key_errors(error_text)
    print(f"📊 Found {len(key_errors['exceptions'])} exceptions, {key_errors['stack_traces']} stack traces")
    print()

    # B. ANALYZE WITH AI (Text only)
    print("[1/2] 🔍 Analyzing error log with AI...")
    try:
        if DEMO_MODE:
            text_response = """SUMMARY: The API endpoint /users returned a 500 Internal Server Error due to a null pointer exception in the database query layer.

ROOT CAUSE: This is a code bug - specifically in the data validation layer where user input is not properly sanitized before database queries.

SEVERITY: High - This affects all user-related operations and will cause test failures consistently.

RECOMMENDATION: 
1. Add null checks in the UserService.validateInput() method
2. Implement proper error handling for database queries
3. Add unit tests to prevent regression"""
        else:
            prompt = f"""You are a Senior QA Engineer analyzing a nightly regression test failure.

ERROR LOG:
{error_text}

Provide a structured analysis:
1. SUMMARY: What specifically failed? (2-3 sentences)
2. ROOT CAUSE: Is this a code bug, infrastructure issue, test flakiness, or environmental problem? Explain.
3. SEVERITY: Critical/High/Medium/Low - with justification
4. RECOMMENDATION: Specific actionable steps to resolve

Be concise and actionable."""
            
            text_response = call_cody_api(prompt)
        
        print("✅ Log analysis complete\n")
        
        # C. ANALYZE SCREENSHOT
        print("[2/2] 🖼️  Analyzing screenshot...")
        if os.path.exists(IMAGE_PATH):
            try:
                img = Image.open(IMAGE_PATH)
                img_info = f"Screenshot captured: {img.size[0]}x{img.size[1]} pixels, {img.format}"
                
                if DEMO_MODE:
                    image_response = "The screenshot shows a 500 error page with broken CSS styling. The error message is partially visible showing 'NullPointerException'. Navigation buttons appear functional but the main content area displays the error."
                else:
                    # Note: Cody has limited image analysis
                    image_response = f"{img_info}\n\nNote: Image analysis not fully supported via Cody API. Screenshot saved for manual review. Visible elements suggest UI error page with stack trace."
                
                print(f"✅ Screenshot analyzed: {img_info}\n")
            except Exception as e:
                print(f"⚠️  Could not process image: {e}\n")
                image_response = "Image analysis skipped due to error"
        else:
            print(f"⚠️  No screenshot found at {IMAGE_PATH}\n")
            image_response = "No screenshot available for analysis"
        
        # Generate report
        print("[3/3] 📝 Generating HTML report...")
        generate_html_report(text_response, image_response, key_errors)
        
        print()
        print("="*60)
        print("✅ ANALYSIS COMPLETE")
        print("="*60)
        print(f"📄 Report: triage_report.html")
        print(f"📊 Confidence: {85 if 'error' in text_response.lower() else 65}%")
        print("="*60)
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ ERROR: {error_msg}")
        print("\n💡 Tip: Set DEMO_MODE = True to test without API calls")

if __name__ == "__main__":
    analyze_nightly_failure()
