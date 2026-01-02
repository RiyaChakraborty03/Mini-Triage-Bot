"""
Advanced Mini-Triage Bot - Production Ready
Automates nightly regression log analysis using Sourcegraph Cody AI
Handles multiple log files, batch processing, and detailed reporting
"""

import os
import sys
import requests
from PIL import Image
import json
from datetime import datetime
from dotenv import load_dotenv
import re
import traceback
from pathlib import Path
import hashlib

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

DEMO_MODE = False  # Set to True for testing without API calls
LOGS_DIR = "logs"
REPORTS_DIR = "reports"
ARCHIVE_DIR = "reports/archive"
MAX_LOG_SIZE = 50000  # Maximum characters to send to API (to avoid token limits)
RETRY_ATTEMPTS = 3
TIMEOUT = 30

# Create necessary directories
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

class TriageLogger:
    """Custom logger for triage operations"""
    def __init__(self, log_file=None):
        self.log_file = log_file or os.path.join(REPORTS_DIR, f"triage_log_{datetime.now().strftime('%Y%m%d')}.log")
        
    def log(self, level, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}\n"
        print(f"[{level}] {message}")
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)

logger = TriageLogger()

def call_cody_api(prompt, retry_count=0):
    """Call Sourcegraph Cody API with retry logic and error handling"""
    payload = {
        "messages": [
            {
                "speaker": "human",
                "text": prompt
            }
        ],
        "maxTokensToSample": 2000,
        "temperature": 0.2  # Lower temperature for more consistent analysis
    }
    
    try:
        logger.log("DEBUG", f"Calling Cody API (attempt {retry_count + 1}/{RETRY_ATTEMPTS})")
        response = requests.post(
            CODY_API_URL, 
            headers=HEADERS, 
            json=payload, 
            stream=True,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        # Collect streamed response
        full_response = ""
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data: '):
                    data = decoded_line[6:]  # Remove 'data: ' prefix
                    if data and data != '[DONE]':
                        try:
                            chunk = json.loads(data)
                            if 'completion' in chunk:
                                full_response += chunk['completion']
                        except json.JSONDecodeError:
                            continue
        
        if not full_response.strip():
            raise Exception("Empty response from API")
            
        logger.log("DEBUG", "API call successful")
        return full_response.strip()
        
    except requests.exceptions.Timeout:
        logger.log("WARNING", f"API timeout (attempt {retry_count + 1})")
        if retry_count < RETRY_ATTEMPTS - 1:
            return call_cody_api(prompt, retry_count + 1)
        return "Error: API timeout after multiple attempts"
        
    except requests.exceptions.RequestException as e:
        logger.log("ERROR", f"API request failed: {str(e)}")
        if retry_count < RETRY_ATTEMPTS - 1:
            return call_cody_api(prompt, retry_count + 1)
        return f"Error calling Cody API: {str(e)}"
        
    except Exception as e:
        logger.log("ERROR", f"Unexpected error: {str(e)}")
        return f"Error: {str(e)}"

def extract_error_patterns(log_text):
    """Extract common error patterns from logs"""
    patterns = {
        'exceptions': re.findall(r'(\w+Exception|Error):\s*(.+)', log_text),
        'stack_traces': re.findall(r'at\s+[\w\.\$]+\([\w\.]+:\d+\)', log_text),
        'failed_tests': re.findall(r'(FAILED|FAIL|ERROR)\s+(.+)', log_text, re.IGNORECASE),
        'warnings': re.findall(r'(WARNING|WARN)\s*:\s*(.+)', log_text, re.IGNORECASE),
        'assertions': re.findall(r'Assert(?:ion)?(?:Error)?:\s*(.+)', log_text),
        'timeouts': re.findall(r'timeout|timed out', log_text, re.IGNORECASE),
        'null_pointers': re.findall(r'null\s*pointer|NullPointerException', log_text, re.IGNORECASE),
        'connection_errors': re.findall(r'connection\s+(?:refused|failed|timeout)', log_text, re.IGNORECASE)
    }
    
    return {k: v for k, v in patterns.items() if v}

def categorize_failure(log_text, error_patterns):
    """Categorize the type of failure"""
    categories = []
    
    if error_patterns.get('exceptions'):
        categories.append("Exception/Error")
    if error_patterns.get('failed_tests'):
        categories.append("Test Failure")
    if error_patterns.get('timeouts'):
        categories.append("Timeout")
    if error_patterns.get('null_pointers'):
        categories.append("Null Pointer")
    if error_patterns.get('connection_errors'):
        categories.append("Connection Issue")
    if error_patterns.get('assertions'):
        categories.append("Assertion Failure")
        
    return categories if categories else ["Unknown"]

def read_error_log(log_path):
    """Read error log file with size limits"""
    try:
        with open(log_path, "r", encoding="utf-8", errors='ignore') as f:
            content = f.read()
            
        # If log is too large, truncate intelligently
        if len(content) > MAX_LOG_SIZE:
            logger.log("WARNING", f"Log file too large ({len(content)} chars), truncating to {MAX_LOG_SIZE}")
            # Keep first and last portions
            half = MAX_LOG_SIZE // 2
            content = content[:half] + "\n\n... [TRUNCATED] ...\n\n" + content[-half:]
            
        return content
    except FileNotFoundError:
        logger.log("ERROR", f"{log_path} not found!")
        return None
    except Exception as e:
        logger.log("ERROR", f"Error reading {log_path}: {str(e)}")
        return None

def get_confidence_score(text, error_patterns):
    """Calculate confidence score based on AI response and error patterns"""
    score = 50  # Base score
    
    # Increase confidence based on keywords
    if "critical" in text.lower():
        score += 20
    if "error" in text.lower() or "exception" in text.lower():
        score += 15
    if "bug" in text.lower():
        score += 10
    if "warning" in text.lower():
        score += 5
        
    # Increase based on error patterns found
    if error_patterns.get('exceptions'):
        score += 10
    if error_patterns.get('stack_traces'):
        score += 10
    if error_patterns.get('failed_tests'):
        score += 5
        
    # Decrease if uncertain language
    if "might" in text.lower() or "possibly" in text.lower() or "unclear" in text.lower():
        score -= 10
        
    return min(max(score, 0), 100)  # Clamp between 0-100

def analyze_log(error_text, log_filename):
    """Analyze error log text with enhanced prompting"""
    if DEMO_MODE:
        return {
            'summary': "Demo analysis: The API endpoint returned a 500 error due to null pointer exception.",
            'root_cause': "Code bug in the data validation layer",
            'severity': "High",
            'recommendation': "Fix null pointer handling in validation code"
        }
    
    try:
        # Extract error patterns first
        error_patterns = extract_error_patterns(error_text)
        categories = categorize_failure(error_text, error_patterns)
        
        # Build context-aware prompt
        prompt = f"""You are an expert QA Engineer analyzing a nightly regression test failure.

LOG FILE: {log_filename}
DETECTED CATEGORIES: {', '.join(categories)}

ERROR LOG:
{error_text}

Please provide a detailed analysis in the following format:

1. SUMMARY: What specifically failed? (2-3 sentences)
2. ROOT CAUSE: Is this a code bug, infrastructure issue, test flakiness, or environmental problem? Explain why.
3. SEVERITY: Critical/High/Medium/Low - with justification
4. RECOMMENDATION: Specific next steps to resolve this issue
5. AFFECTED COMPONENTS: Which parts of the system are impacted?
6. REPRODUCIBILITY: Is this likely reproducible or intermittent?

Be specific and actionable."""
        
        response = call_cody_api(prompt)
        
        # Parse structured response
        analysis = {
            'summary': extract_section(response, 'SUMMARY'),
            'root_cause': extract_section(response, 'ROOT CAUSE'),
            'severity': extract_section(response, 'SEVERITY'),
            'recommendation': extract_section(response, 'RECOMMENDATION'),
            'affected_components': extract_section(response, 'AFFECTED COMPONENTS'),
            'reproducibility': extract_section(response, 'REPRODUCIBILITY'),
            'full_response': response,
            'error_patterns': error_patterns,
            'categories': categories
        }
        
        return analysis
        
    except Exception as e:
        logger.log("ERROR", f"Error analyzing log: {str(e)}\n{traceback.format_exc()}")
        return {
            'summary': f"Error during analysis: {str(e)}",
            'root_cause': "Analysis failed",
            'severity': "Unknown",
            'recommendation': "Manual review required",
            'full_response': str(e)
        }

def extract_section(text, section_name):
    """Extract a specific section from structured AI response"""
    pattern = rf"{section_name}:?\s*(.+?)(?=\n\d+\.|$)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return "Not provided"

def analyze_image(image_path):
    """Analyze failure screenshot with metadata"""
    if not os.path.exists(image_path):
        return None
    
    try:
        img = Image.open(image_path)
        metadata = {
            'format': img.format,
            'size': img.size,
            'mode': img.mode,
            'file_size': os.path.getsize(image_path)
        }
        
        if DEMO_MODE:
            return {
                'analysis': "Demo: Screenshot shows 500 error page with broken CSS styling",
                'metadata': metadata
            }
        
        # Note: Cody API has limited image analysis
        return {
            'analysis': "Image analysis not fully supported via Cody API. Manual review recommended.",
            'metadata': metadata,
            'note': "Screenshot captured and stored for manual review"
        }
        
    except Exception as e:
        logger.log("ERROR", f"Error analyzing image: {str(e)}")
        return None

def generate_json_report(analysis, image_analysis, confidence_score, log_file, image_file):
    """Generate comprehensive JSON report"""
    timestamp = datetime.now().isoformat()
    
    report = {
        "metadata": {
            "timestamp": timestamp,
            "report_version": "2.0",
            "triage_bot_version": "1.0-production",
            "analysis_mode": "DEMO" if DEMO_MODE else "LIVE"
        },
        "files": {
            "log_file": log_file,
            "log_size": os.path.getsize(log_file) if os.path.exists(log_file) else 0,
            "image_file": image_file,
            "log_hash": hashlib.md5(open(log_file, 'rb').read()).hexdigest() if os.path.exists(log_file) else None
        },
        "analysis": {
            "summary": analysis.get('summary', 'N/A'),
            "root_cause": analysis.get('root_cause', 'N/A'),
            "severity": analysis.get('severity', 'Unknown'),
            "recommendation": analysis.get('recommendation', 'N/A'),
            "affected_components": analysis.get('affected_components', 'N/A'),
            "reproducibility": analysis.get('reproducibility', 'N/A'),
            "categories": analysis.get('categories', []),
            "error_patterns": {k: len(v) if isinstance(v, list) else v for k, v in analysis.get('error_patterns', {}).items()}
        },
        "image_analysis": image_analysis,
        "confidence_score": confidence_score,
        "priority": get_priority(confidence_score, analysis.get('severity', 'Unknown')),
        "recommendation_summary": get_recommendation_summary(confidence_score, analysis.get('severity', 'Unknown')),
        "next_steps": generate_next_steps(analysis)
    }
    
    report_file = os.path.join(REPORTS_DIR, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.log("INFO", f"JSON report saved: {report_file}")
    return report_file

def get_priority(confidence, severity):
    """Calculate priority level"""
    severity_map = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
    sev_score = severity_map.get(severity.lower().split()[0], 2)
    conf_score = confidence / 25  # 0-4 scale
    
    total = (sev_score + conf_score) / 2
    
    if total >= 3.5:
        return "P0 - Critical"
    elif total >= 2.5:
        return "P1 - High"
    elif total >= 1.5:
        return "P2 - Medium"
    else:
        return "P3 - Low"

def get_recommendation_summary(confidence, severity):
    """Generate recommendation summary"""
    if confidence >= 80 and 'critical' in severity.lower():
        return "IMMEDIATE ACTION REQUIRED - High confidence critical issue detected"
    elif confidence >= 75:
        return "Review and address soon - Likely reproducible issue"
    elif confidence >= 50:
        return "Investigate further - Moderate confidence in analysis"
    else:
        return "Manual review recommended - Low confidence or unclear failure"

def generate_next_steps(analysis):
    """Generate actionable next steps"""
    steps = []
    
    severity = analysis.get('severity', '').lower()
    root_cause = analysis.get('root_cause', '').lower()
    
    if 'critical' in severity or 'high' in severity:
        steps.append("1. Notify development team immediately")
        steps.append("2. Create high-priority bug ticket")
    
    if 'code bug' in root_cause or 'bug' in root_cause:
        steps.append("3. Assign to development team for code fix")
        steps.append("4. Add regression test to prevent recurrence")
    elif 'infrastructure' in root_cause or 'environmental' in root_cause:
        steps.append("3. Escalate to DevOps/Infrastructure team")
        steps.append("4. Review environment configuration")
    elif 'flaky' in root_cause or 'intermittent' in root_cause:
        steps.append("3. Investigate test stability")
        steps.append("4. Consider adding retry logic or fixing race conditions")
    
    steps.append("5. Re-run test to verify fix")
    steps.append("6. Update test documentation if needed")
    
    return steps

def generate_html_report(analysis, image_analysis, confidence_score, log_file, image_file):
    """Generate production-quality HTML report"""
    log_safe = analysis.get('full_response', 'No analysis').replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    
    severity = analysis.get('severity', 'Unknown')
    categories = ', '.join(analysis.get('categories', ['Unknown']))
    error_patterns = analysis.get('error_patterns', {})
    
    # Determine colors based on severity and confidence
    if confidence_score >= 80:
        conf_color = "green"
    elif confidence_score >= 60:
        conf_color = "orange"
    else:
        conf_color = "red"
    
    if 'critical' in severity.lower():
        sev_color = "#dc3545"
    elif 'high' in severity.lower():
        sev_color = "#fd7e14"
    elif 'medium' in severity.lower():
        sev_color = "#ffc107"
    else:
        sev_color = "#28a745"
    
    priority = get_priority(confidence_score, severity)
    next_steps = generate_next_steps(analysis)
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nightly Regression Triage Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ 
            max-width: 1200px; 
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
        .header h1 {{ font-size: 32px; margin-bottom: 10px; }}
        .header p {{ opacity: 0.9; font-size: 14px; }}
        .alert-banner {{
            background: {sev_color};
            color: white;
            padding: 15px 30px;
            text-align: center;
            font-weight: bold;
            font-size: 18px;
        }}
        .content {{ padding: 30px; }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .metric-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            text-align: center;
        }}
        .metric-card h3 {{ color: #666; font-size: 14px; margin-bottom: 10px; }}
        .metric-card .value {{ font-size: 28px; font-weight: bold; color: #333; }}
        .section {{ 
            margin: 20px 0; 
            padding: 25px; 
            border-left: 5px solid #667eea;
            background: #f8f9fa;
            border-radius: 5px;
        }}
        .section h2 {{ 
            color: #333;
            margin-bottom: 15px;
            font-size: 22px;
            display: flex;
            align-items: center;
        }}
        .section h2::before {{
            content: '▶';
            margin-right: 10px;
            color: #667eea;
        }}
        .section p, .section ul {{ 
            color: #555;
            line-height: 1.8;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .section ul {{
            margin-left: 20px;
            margin-top: 10px;
        }}
        .section li {{
            margin-bottom: 8px;
        }}
        .summary-section {{ border-left-color: #007bff; }}
        .root-cause-section {{ border-left-color: #dc3545; }}
        .recommendation-section {{ border-left-color: #28a745; }}
        .patterns-section {{ border-left-color: #ffc107; }}
        .confidence-section {{ 
            border-left-color: {conf_color};
            background: linear-gradient(135deg, rgba(0,0,0,0.02), rgba(0,0,0,0.05));
        }}
        .confidence-score {{
            font-size: 48px;
            font-weight: bold;
            color: {conf_color};
            text-align: center;
            margin: 20px 0;
        }}
        .priority-badge {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            background: {sev_color};
            color: white;
            font-weight: bold;
            margin: 10px 0;
        }}
        .error-patterns {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        .pattern-item {{
            background: white;
            padding: 15px;
            border-radius: 5px;
            border: 1px solid #ddd;
        }}
        .pattern-item strong {{ color: #667eea; }}
        .next-steps {{
            background: white;
            padding: 20px;
            border-radius: 5px;
            margin-top: 15px;
        }}
        .next-steps ol {{
            margin-left: 20px;
        }}
        .next-steps li {{
            margin-bottom: 10px;
            line-height: 1.6;
        }}
        .metadata {{
            font-size: 12px;
            color: #999;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 2px solid #eee;
        }}
        .metadata table {{
            width: 100%;
            margin-top: 10px;
        }}
        .metadata td {{
            padding: 5px;
        }}
        .metadata td:first-child {{
            font-weight: bold;
            width: 200px;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px 30px;
            text-align: center;
            color: #666;
            font-size: 12px;
        }}
        .tag {{
            display: inline-block;
            padding: 4px 12px;
            margin: 4px;
            background: #667eea;
            color: white;
            border-radius: 12px;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Nightly Regression Triage Report</h1>
            <p>Automated AI-Powered Failure Analysis | Production Ready</p>
        </div>
        
        <div class="alert-banner">
            {priority} | Severity: {severity}
        </div>
        
        <div class="content">
            <div class="metrics">
                <div class="metric-card">
                    <h3>Confidence Score</h3>
                    <div class="value" style="color: {conf_color};">{confidence_score}%</div>
                </div>
                <div class="metric-card">
                    <h3>Severity Level</h3>
                    <div class="value" style="color: {sev_color};">{severity}</div>
                </div>
                <div class="metric-card">
                    <h3>Priority</h3>
                    <div class="value">{priority.split('-')[0]}</div>
                </div>
                <div class="metric-card">
                    <h3>Categories</h3>
                    <div class="value" style="font-size: 16px;">{len(analysis.get('categories', []))}</div>
                </div>
            </div>
            
            <div class="section summary-section">
                <h2>Executive Summary</h2>
                <p>{analysis.get('summary', 'No summary available')}</p>
                <div style="margin-top: 15px;">
                    <strong>Categories:</strong><br>
                    {' '.join([f'<span class="tag">{cat}</span>' for cat in analysis.get('categories', [])])}
                </div>
            </div>
            
            <div class="section root-cause-section">
                <h2>Root Cause Analysis</h2>
                <p>{analysis.get('root_cause', 'Not determined')}</p>
                <p style="margin-top: 10px;"><strong>Reproducibility:</strong> {analysis.get('reproducibility', 'Unknown')}</p>
                <p><strong>Affected Components:</strong> {analysis.get('affected_components', 'Not specified')}</p>
            </div>
            
            <div class="section patterns-section">
                <h2>Detected Error Patterns</h2>
                <div class="error-patterns">
                    {generate_pattern_html(error_patterns)}
                </div>
            </div>
            
            <div class="section recommendation-section">
                <h2>Recommendations & Next Steps</h2>
                <p><strong>Primary Recommendation:</strong></p>
                <p>{analysis.get('recommendation', 'Manual review required')}</p>
                
                <div class="next-steps">
                    <h3 style="margin-bottom: 10px;">Action Items:</h3>
                    <ol>
                        {generate_steps_html(next_steps)}
                    </ol>
                </div>
            </div>
            
            <div class="section confidence-section">
                <h2>Confidence Assessment</h2>
                <div class="confidence-score">{confidence_score}%</div>
                <p style="text-align: center;">
                    <strong>{get_recommendation_summary(confidence_score, severity)}</strong>
                </p>
            </div>
            
            <div class="section">
                <h2>Full AI Analysis</h2>
                <p style="background: white; padding: 15px; border-radius: 5px; font-family: monospace; font-size: 13px;">{log_safe}</p>
            </div>
            
            <div class="metadata">
                <h3 style="color: #333; margin-bottom: 10px;">Report Metadata</h3>
                <table>
                    <tr><td>Generated:</td><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
                    <tr><td>Log File:</td><td>{log_file}</td></tr>
                    <tr><td>Log Size:</td><td>{os.path.getsize(log_file) if os.path.exists(log_file) else 0} bytes</td></tr>
                    <tr><td>Screenshot:</td><td>{image_file if image_file else 'None'}</td></tr>
                    <tr><td>Analysis Mode:</td><td>{'DEMO MODE' if DEMO_MODE else 'LIVE API'}</td></tr>
                    <tr><td>Report Version:</td><td>2.0 Production</td></tr>
                </table>
            </div>
        </div>
        
        <div class="footer">
            <p>Mini-Triage Bot v2.0 Production | Powered by Sourcegraph Cody AI</p>
            <p>NXP Internal Tool | Automated Nightly Regression Analysis</p>
        </div>
    </div>
</body>
</html>"""
    
    report_file = os.path.join(REPORTS_DIR, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    logger.log("INFO", f"HTML report saved: {report_file}")
    return report_file

def generate_pattern_html(patterns):
    """Generate HTML for error patterns"""
    if not patterns:
        return '<div class="pattern-item">No specific patterns detected</div>'
    
    html = ""
    for pattern_type, items in patterns.items():
        count = len(items) if isinstance(items, list) else 1
        html += f'<div class="pattern-item"><strong>{pattern_type.replace("_", " ").title()}:</strong> {count} occurrence(s)</div>'
    
    return html

def generate_steps_html(steps):
    """Generate HTML for next steps"""
    return '\n'.join([f'<li>{step}</li>' for step in steps])

def batch_analyze_logs(log_dir=LOGS_DIR):
    """Analyze multiple log files in batch"""
    logger.log("INFO", f"Starting batch analysis of logs in {log_dir}")
    
    log_files = [f for f in os.listdir(log_dir) if f.endswith('.txt')]
    
    if not log_files:
        logger.log("WARNING", "No log files found for analysis")
        return []
    
    logger.log("INFO", f"Found {len(log_files)} log file(s) to analyze")
    
    results = []
    for log_file in log_files:
        logger.log("INFO", f"Analyzing: {log_file}")
        result = run_triage(os.path.join(log_dir, log_file))
        if result:
            results.append(result)
    
    # Generate summary report
    generate_batch_summary(results)
    
    return results

def generate_batch_summary(results):
    """Generate summary report for batch analysis"""
    if not results:
        return
    
    summary_file = os.path.join(REPORTS_DIR, f"batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
    
    total = len(results)
    critical = sum(1 for r in results if 'critical' in r.get('severity', '').lower())
    high = sum(1 for r in results if 'high' in r.get('severity', '').lower())
    medium = sum(1 for r in results if 'medium' in r.get('severity', '').lower())
    low = total - critical - high - medium
    
    avg_confidence = sum(r.get('confidence', 0) for r in results) / total if total > 0 else 0
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Batch Analysis Summary</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
        h1 {{ color: #333; border-bottom: 3px solid #667eea; padding-bottom: 10px; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0; }}
        .summary-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; }}
        .summary-card h3 {{ margin: 0; font-size: 14px; opacity: 0.9; }}
        .summary-card .value {{ font-size: 36px; font-weight: bold; margin-top: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #667eea; color: white; }}
        tr:hover {{ background: #f5f5f5; }}
        .critical {{ color: #dc3545; font-weight: bold; }}
        .high {{ color: #fd7e14; font-weight: bold; }}
        .medium {{ color: #ffc107; font-weight: bold; }}
        .low {{ color: #28a745; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Batch Analysis Summary Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="summary-grid">
            <div class="summary-card">
                <h3>Total Analyzed</h3>
                <div class="value">{total}</div>
            </div>
            <div class="summary-card" style="background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);">
                <h3>Critical</h3>
                <div class="value">{critical}</div>
            </div>
            <div class="summary-card" style="background: linear-gradient(135deg, #fd7e14 0%, #e8590c 100%);">
                <h3>High</h3>
                <div class="value">{high}</div>
            </div>
            <div class="summary-card" style="background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%);">
                <h3>Medium</h3>
                <div class="value">{medium}</div>
            </div>
            <div class="summary-card" style="background: linear-gradient(135deg, #28a745 0%, #218838 100%);">
                <h3>Low</h3>
                <div class="value">{low}</div>
            </div>
            <div class="summary-card">
                <h3>Avg Confidence</h3>
                <div class="value">{avg_confidence:.0f}%</div>
            </div>
        </div>
        
        <h2>Detailed Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Log File</th>
                    <th>Severity</th>
                    <th>Confidence</th>
                    <th>Priority</th>
                    <th>Categories</th>
                    <th>Report</th>
                </tr>
            </thead>
            <tbody>
"""
    
    for result in results:
        severity = result.get('severity', 'Unknown')
        sev_class = severity.lower().split()[0] if severity != 'Unknown' else 'low'
        
        html += f"""
                <tr>
                    <td>{result.get('log_file', 'N/A')}</td>
                    <td class="{sev_class}">{severity}</td>
                    <td>{result.get('confidence', 0)}%</td>
                    <td>{result.get('priority', 'N/A')}</td>
                    <td>{', '.join(result.get('categories', []))}</td>
                    <td><a href="{result.get('html_report', '#')}">View Report</a></td>
                </tr>
"""
    
    html += """
            </tbody>
        </table>
    </div>
</body>
</html>"""
    
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(html)
    
    logger.log("INFO", f"Batch summary saved: {summary_file}")
    print(f"\n{'='*60}")
    print(f"BATCH ANALYSIS COMPLETE")
    print(f"{'='*60}")
    print(f"Total Analyzed: {total}")
    print(f"Critical: {critical} | High: {high} | Medium: {medium} | Low: {low}")
    print(f"Average Confidence: {avg_confidence:.1f}%")
    print(f"Summary Report: {summary_file}")
    print(f"{'='*60}\n")

def run_triage(log_file=None, image_file=None):
    """Main triage function - enhanced for production"""
    logger.log("INFO", "=== Mini-Triage Bot Starting ===")
    
    # Find log file
    if not log_file:
        for file in os.listdir(LOGS_DIR) if os.path.exists(LOGS_DIR) else []:
            if file.endswith('.txt'):
                log_file = os.path.join(LOGS_DIR, file)
                break
    
    if not log_file or not os.path.exists(log_file):
        logger.log("ERROR", "No log file found!")
        return None
    
    # Find image file
    if not image_file:
        for file in os.listdir(LOGS_DIR) if os.path.exists(LOGS_DIR) else []:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_file = os.path.join(LOGS_DIR, file)
                break
    
    logger.log("INFO", f"Analyzing: {log_file}")
    if image_file:
        logger.log("INFO", f"Screenshot: {image_file}")
    
    # Read and analyze
    error_text = read_error_log(log_file)
    if not error_text:
        return None
    
    logger.log("INFO", "[1/3] Analyzing error log...")
    analysis = analyze_log(error_text, os.path.basename(log_file))
    logger.log("INFO", "Log analysis complete")
    
    logger.log("INFO", "[2/3] Analyzing screenshot...")
    image_analysis = None
    if image_file and os.path.exists(image_file):
        image_analysis = analyze_image(image_file)
        logger.log("INFO", "Image analysis complete")
    else:
        logger.log("WARNING", "No image found - skipping image analysis")
    
    # Calculate confidence
    error_patterns = analysis.get('error_patterns', {})
    confidence = get_confidence_score(analysis.get('full_response', ''), error_patterns)
    
    logger.log("INFO", "[3/3] Generating reports...")
    
    # Generate both report formats
    html_report = generate_html_report(
        analysis, 
        image_analysis or "No image analysis", 
        confidence, 
        log_file, 
        image_file
    )
    
    json_report = generate_json_report(
        analysis, 
        image_analysis or "No image analysis", 
        confidence,
        log_file, 
        image_file
    )
    
    logger.log("INFO", "Reports generated successfully")
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"ANALYSIS COMPLETE")
    print(f"{'='*60}")
    print(f"Log File: {log_file}")
    print(f"Severity: {analysis.get('severity', 'Unknown')}")
    print(f"Confidence: {confidence}%")
    print(f"Priority: {get_priority(confidence, analysis.get('severity', 'Unknown'))}")
    print(f"Categories: {', '.join(analysis.get('categories', []))}")
    print(f"\nReports:")
    print(f"  - HTML: {html_report}")
    print(f"  - JSON: {json_report}")
    print(f"{'='*60}\n")
    
    return {
        'log_file': log_file,
        'severity': analysis.get('severity', 'Unknown'),
        'confidence': confidence,
        'priority': get_priority(confidence, analysis.get('severity', 'Unknown')),
        'categories': analysis.get('categories', []),
        'html_report': html_report,
        'json_report': json_report
    }

def cleanup_old_reports(days=7):
    """Archive old reports"""
    logger.log("INFO", f"Cleaning up reports older than {days} days")
    
    cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
    archived = 0
    
    for file in os.listdir(REPORTS_DIR):
        if file.startswith('report_'):
            filepath = os.path.join(REPORTS_DIR, file)
            if os.path.getmtime(filepath) < cutoff:
                archive_path = os.path.join(ARCHIVE_DIR, file)
                os.rename(filepath, archive_path)
                archived += 1
    
    logger.log("INFO", f"Archived {archived} old report(s)")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Mini-Triage Bot - Production Ready')
    parser.add_argument('--log', help='Specific log file to analyze')
    parser.add_argument('--image', help='Specific image file to analyze')
    parser.add_argument('--batch', action='store_true', help='Analyze all logs in batch mode')
    parser.add_argument('--cleanup', type=int, help='Archive reports older than N days')
    parser.add_argument('--demo', action='store_true', help='Run in demo mode (no API calls)')
    
    args = parser.parse_args()
    
    if args.demo:
        DEMO_MODE = True
        logger.log("INFO", "Running in DEMO MODE")
    
    if args.cleanup:
        cleanup_old_reports(args.cleanup)
    elif args.batch:
        batch_analyze_logs()
    else:
        run_triage(args.log, args.image)

def extract_relevant_context(log_content, context_lines=20):
    """Extract relevant context around ERROR and EXCEPTION keywords to reduce token count"""
    if not log_content:
        return log_content
    
    lines = log_content.split('\n')
    relevant_indices = set()
    
    # Find all lines with ERROR or EXCEPTION
    for i, line in enumerate(lines):
        if 'ERROR' in line.upper() or 'EXCEPTION' in line.upper():
            # Add the error line and surrounding context
            start = max(0, i - context_lines)
            end = min(len(lines), i + context_lines + 1)
            relevant_indices.update(range(start, end))
    
    # If no errors found, return first 100 lines to avoid sending entire log
    if not relevant_indices:
        return '\n'.join(lines[:100])
    
    # Sort indices and extract relevant lines
    sorted_indices = sorted(relevant_indices)
    relevant_lines = []
    
    for idx in sorted_indices:
        relevant_lines.append(lines[idx])
    
    return '\n'.join(relevant_lines)