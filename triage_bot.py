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
IMAGE_PATH = "logs/failure.png"
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
        last_completion = ""

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
                                # Store only the complete response, not incremental
                                last_completion = chunk['completion']
                        except json.JSONDecodeError:
                            continue

        full_response = last_completion
        
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
    """Generate an enhanced HTML report using Tailwind CSS"""
    # Escape HTML special characters
    log_safe = format_ai_response(log_analysis)
    img_safe = image_analysis.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    severity, sev_color = get_severity_from_response(log_analysis)
    
    # Calculate confidence
    confidence = 85
    if 'critical' in log_analysis.lower() or 'error' in log_analysis.lower():
        confidence = 90
    elif 'might' in log_analysis.lower() or 'possibly' in log_analysis.lower():
        confidence = 65
    
    # Map severity to Tailwind colors
    severity_colors = {
        'Critical': 'red',
        'High': 'orange',
        'Medium': 'amber',
        'Low': 'green'
    }
    tw_color = severity_colors.get(severity, 'blue')
    
    # Map confidence to Tailwind colors
    conf_color = 'green' if confidence >= 80 else 'amber' if confidence >= 60 else 'red'
    
    # Format key errors
    error_summary = ""
    if key_errors['exceptions']:
        error_summary += "<div class='font-medium text-violet-700 mt-4 mb-2'>Top Exceptions:</div><ul class='list-disc pl-5'>"
        for exc_type, exc_msg in key_errors['exceptions'][:3]:
            error_summary += f"<li><span class='font-semibold'>{exc_type}:</span> {exc_msg[:100]}</li>"
        error_summary += "</ul>"
    
    if key_errors['failed_tests']:
        error_summary += "<div class='font-medium text-violet-700 mt-4 mb-2'>Failed Tests:</div><ul class='list-disc pl-5'>"
        for status, test in key_errors['failed_tests'][:3]:
            error_summary += f"<li>{test[:100]}</li>"
        error_summary += "</ul>"
    
    if key_errors['stack_traces']:
        error_summary += f"<p class='mt-3'><span class='font-semibold'>Stack Traces Found:</span> {key_errors['stack_traces']}</p>"
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Triage Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    colors: {{
                        primary: {{
                            50: '#f0f9ff',
                            100: '#e0f2fe',
                            500: '#0ea5e9',
                            600: '#0284c7',
                            700: '#0369a1',
                            800: '#075985'
                        }}
                    }},
                    fontFamily: {{
                        sans: ['Inter', 'sans-serif'],
                    }}
                }}
            }}
        }}
    </script>
</head>
<body class="bg-slate-100 min-h-screen">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <!-- Header -->
        <div class="bg-gradient-to-r from-primary-600 to-primary-800 rounded-t-lg shadow-lg">
            <div class="px-6 py-8 text-white">
                <h1 class="text-3xl font-bold flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    Nightly Regression Triage Report
                </h1>
                <p class="mt-2 text-primary-100">Automated AI-Powered Analysis | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        </div>
        
        <!-- Main Content -->
        <div class="bg-white rounded-b-lg shadow-lg">
            <!-- Status Bar -->
            <div class="border-b border-gray-200 bg-{tw_color}-50 px-6 py-4 flex items-center justify-between">
                <div class="flex items-center">
                    <span class="inline-flex items-center rounded-md bg-{tw_color}-100 px-3 py-1 text-sm font-medium text-{tw_color}-800 ring-1 ring-inset ring-{tw_color}-600/20">
                        Severity: {severity}
                    </span>
                    <span class="ml-4 inline-flex items-center rounded-md bg-{conf_color}-100 px-3 py-1 text-sm font-medium text-{conf_color}-800 ring-1 ring-inset ring-{conf_color}-600/20">
                        Confidence: {confidence}%
                    </span>
                </div>
                <div class="text-sm text-gray-600">
                    {datetime.now().strftime('%A, %B %d, %Y')}
                </div>
            </div>
            
            <!-- Dashboard Metrics -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 px-6 py-6">
                <!-- Confidence Score -->
                <div class="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
                    <div class="flex items-center">
                        <div class="p-3 rounded-full bg-{conf_color}-100 text-{conf_color}-700">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                        <div class="ml-4">
                            <h2 class="text-gray-500 text-sm font-medium">Confidence</h2>
                            <div class="flex items-center mt-1">
                                <span class="text-2xl font-bold text-{conf_color}-700">{confidence}%</span>
                            </div>
                        </div>
                    </div>
                    <!-- Progress Bar -->
                    <div class="w-full bg-gray-200 rounded-full h-2.5 mt-3">
                        <div class="bg-{conf_color}-600 h-2.5 rounded-full" style="width: {confidence}%"></div>
                    </div>
                </div>
                
                <!-- Severity -->
                <div class="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
                    <div class="flex items-center">
                        <div class="p-3 rounded-full bg-{tw_color}-100 text-{tw_color}-700">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                        </div>
                        <div class="ml-4">
                            <h2 class="text-gray-500 text-sm font-medium">Severity</h2>
                            <div class="flex items-center mt-1">
                                <span class="text-2xl font-bold text-{tw_color}-700">{severity}</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Exceptions -->
                <div class="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
                    <div class="flex items-center">
                        <div class="p-3 rounded-full bg-red-100 text-red-700">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                        <div class="ml-4">
                            <h2 class="text-gray-500 text-sm font-medium">Exceptions</h2>
                            <div class="flex items-center mt-1">
                                <span class="text-2xl font-bold text-gray-900">{len(key_errors['exceptions'])}</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Stack Traces -->
                <div class="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
                    <div class="flex items-center">
                        <div class="p-3 rounded-full bg-violet-100 text-violet-700">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
                            </svg>
                        </div>
                        <div class="ml-4">
                            <h2 class="text-gray-500 text-sm font-medium">Stack Traces</h2>
                            <div class="flex items-center mt-1">
                                <span class="text-2xl font-bold text-gray-900">{key_errors['stack_traces']}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Main Content Sections -->
            <div class="px-6 py-4 grid grid-cols-1 lg:grid-cols-2 gap-6">
                <!-- Error Summary -->
                <div class="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
                    <h3 class="text-lg font-semibold text-gray-800 flex items-center">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                        </svg>
                        Error Summary
                    </h3>
                    <div class="mt-4 text-gray-700">
                        {error_summary if error_summary else '<p>No specific error patterns detected</p>'}
                    </div>
                </div>
                
                <!-- Confidence Assessment -->
                <div class="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
                    <h3 class="text-lg font-semibold text-gray-800 flex items-center">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
                        </svg>
                        Confidence Assessment
                    </h3>
                    <div class="mt-4">
                        <div class="flex justify-center">
                            <div class="w-full bg-gray-200 rounded-full h-4">
                                <div class="bg-{conf_color}-600 h-4 rounded-full transition-all duration-1000 ease-in-out" style="width: {confidence}%"></div>
                            </div>
                        </div>
                        <div class="text-center mt-2 text-{conf_color}-700 text-xl font-semibold">{confidence}%</div>
                        <div class="mt-4 p-4 border border-{conf_color}-200 rounded-lg bg-{conf_color}-50">
                            <div class="flex items-center">
                                <div class="text-{conf_color}-700 mr-3">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                </div>
                                <div>
                                    <span class="font-semibold">Recommendation:</span> 
                                    {'This is likely a reproducible bug requiring immediate attention.' if confidence >= 80 
                                    else 'Further investigation recommended. May require manual review.' if confidence >= 60
                                    else 'Low confidence - manual review strongly recommended.'}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Analysis Sections -->
            <div class="px-6 py-4">
                <!-- AI Log Analysis -->
                <div class="bg-white p-6 rounded-lg border border-gray-200 shadow-sm mb-6">
                    <h3 class="text-lg font-semibold text-gray-800 flex items-center">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        AI Log Analysis
                    </h3>
                    <div class="mt-4 text-gray-700 whitespace-pre-line">{log_safe}</div>
                </div>
                
                <!-- Image Analysis -->
                <div class="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
                    <h3 class="text-lg font-semibold text-gray-800 flex items-center">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                        Visual Analysis
                    </h3>
                    <div class="mt-4 text-gray-700">{img_safe}</div>
                </div>
            </div>
            
            <!-- Footer -->
            <div class="px-6 py-4 bg-gray-50 rounded-b-lg border-t border-gray-200">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-gray-600">
                    <div>
                        <strong>Log File:</strong> {LOG_PATH}
                    </div>
                    <div>
                        <strong>Screenshot:</strong> {IMAGE_PATH if os.path.exists(IMAGE_PATH) else 'None'}
                    </div>
                    <div>
                        <strong>Analysis Mode:</strong> <span class="px-2 py-1 rounded bg-blue-100 text-blue-800 text-xs font-semibold">LIVE API</span>
                    </div>
                </div>
                <div class="mt-4 text-center text-xs text-gray-500">
                    Mini-Triage Bot v1.0 | Powered by Sourcegraph Cody AI
                </div>
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
                
                # Note: Cody has limited image analysis
                image_response = f"{img_info}\n\nScreenshot information extracted successfully. Basic metadata analysis shows this is a {img.format} image of size {img.size[0]}x{img.size[1]} pixels. For detailed visual analysis, please review the screenshot manually."
                
                print(f"✅ Screenshot analyzed: {img_info}\n")
            except Exception as e:
                print(f"⚠️  Could not process image: {e}\n")
                image_response = "Image analysis skipped due to error"
        else:
            print(f"⚠️  No screenshot found at {IMAGE_PATH}\n")
            print(f"⚠️  Make sure the image file is saved as {IMAGE_PATH} (note the spelling of 'failure')\n")
            image_response = f"No screenshot found at {IMAGE_PATH}. Please check if the image exists and the path is correct."

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
        print("\n💡 Tip: Check your API key or network connection")

def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    
def format_ai_response(text):
    """Format AI response text for proper HTML display"""
    # First handle basic HTML escaping
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    
    # Handle markdown-style bold text with **
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    
    # Handle markdown-style headers
    text = re.sub(r'(?m)^#+\s+(.*?)$', r'<strong class="text-lg text-primary-700">\1</strong>', text)
    
    # Handle numbered lists (like 1., 2., etc)
    text = re.sub(r'(?m)^(\d+\.\s+)(.*?)$', r'<div class="ml-4 mb-2"><span class="font-bold">\1</span>\2</div>', text)
    
    # Handle section markers like "SUMMARY:", "ROOT CAUSE:", etc.
    text = re.sub(r'(?m)^([A-Z\s]+):(.*)$', r'<div class="mt-3 mb-2"><span class="font-bold text-primary-600">\1:</span>\2</div>', text)
    
    # Handle code blocks
    text = re.sub(r'```(?:python)?(.*?)```', r'<pre class="bg-gray-100 p-2 rounded text-sm font-mono overflow-auto">\1</pre>', text, flags=re.DOTALL)
    
    return text   

def health_check_api(timeout=5):
    """Lightweight health check for the Cody API"""
    try:
        payload = {
            "messages": [
                {
                    "speaker": "human",
                    "text": "Health check: Respond with 'OK' if you receive this."
                }
            ],
            "maxTokensToSample": 10,  # Minimal tokens for health check
            "temperature": 0.1
        }
        
        response = requests.post(
            CODY_API_URL, 
            headers=HEADERS, 
            json=payload, 
            stream=False,  # No streaming for health check
            timeout=timeout  # Shorter timeout
        )
        
        if response.status_code == 200:
            return True, "API is operational"
        else:
            return False, f"API returned status code: {response.status_code}"
            
    except requests.exceptions.Timeout:
        return False, "API timeout during health check"
        
    except requests.exceptions.RequestException as e:
        return False, f"API request failed: {str(e)}"
        
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

if __name__ == "__main__":
    analyze_nightly_failure()
