# Mini-Triage Bot 

An AI-powered automated system for analyzing failed test logs and screenshots using Google Gemini API.

## Project Status

✅ **Fully Functional** - All core features implemented and tested

### Completed Features
- **Day 1-2**: Setup & Configuration
  - [x] Python environment configured
  - [x] Google Gemini API key integrated
  - [x] Sample log files and screenshots ready
  
- **Day 3-4**: File Reading
  - [x] Log file reading and parsing
  - [x] Error extraction and display
  
- **Day 5-6**: AI Text Analysis
  - [x] Gemini API integration
  - [x] Error log summarization
  - [x] Root cause detection
  
- **Day 7-8**: Vision/Image Analysis
  - [x] Screenshot processing with PIL
  - [x] Multi-modal AI analysis
  - [x] Visual failure detection
  
- **Day 9**: Report Generation
  - [x] HTML report with styling
  - [x] JSON structured output
  - [x] Confidence scoring (85%+)
  
- **Day 10**: Demo Ready
  - [x] Full automation pipeline
  - [x] Interactive error handling
  - [x] Reusable bot framework

## Setup Instructions

### 1. Install Dependencies
```bash
pip install google-generativeai pillow
```

### 2. API Key Configuration
The API key is already configured in the script:
```python
genai.configure(api_key="AIzaSyDWGWBt5Y1Uabv9oT7fUW6RIDhu6Bs98tI")
```

### 3. Prepare Your Files
Create the following structure:
```
logs/
  ├── fail_log.txt     (your error logs)
  ├── failure.png      (screenshot of failure)
  └── faliure.png      (currently in use)
```

## Usage

### Basic Usage (Standard Version)
```bash
python triage_bot.py
```

This will:
1. Read `logs/fail_log.txt`
2. Analyze the error with Gemini AI
3. Process screenshot if available
4. Generate `triage_report.html`

### Advanced Version (With Extra Features)
```bash
python triage_bot_advanced.py
```

Enhanced features:
- Generates both HTML and JSON reports
- Calculates confidence scores
- Creates timestamped reports in `reports/` directory
- Better error handling and user feedback
- Demo mode for offline testing

## File Structure

```
Mini-Triage-Bot/
├── triage_bot.py                 (main script)
├── triage_bot_advanced.py        (advanced version)
├── triage_report.html            (generated report)
├── README.md                      (this file)
├── logs/
│   ├── fail_log.txt              (error log)
│   └── faliure.png               (failure screenshot)
└── reports/                       (generated reports - advanced mode)
    └── report_*.html             (timestamped reports)
    └── report_*.json             (structured data)
```

## Features

### Log Analysis
- Automatically detects error types
- Identifies root causes (code bug vs infrastructure)
- Categorizes severity levels
- Extracts key failure information

### Image Analysis
- Processes PNG/JPG screenshots
- Detects visual UI issues
- Identifies broken elements
- Flags missing components

### Report Generation
- **HTML Reports**: Beautiful, interactive reports with:
  - Styled analysis sections
  - Confidence scores with visual indicators
  - Recommendations
  - Metadata and timestamps

- **JSON Reports**: Machine-readable format for:
  - Integration with other tools
  - Data archival
  - Programmatic access

### Confidence Scoring
- 0-100% confidence metric
- Based on AI analysis content
- Visual indicator (green/orange/red)
- Actionability recommendations

## Demo Mode

For testing without API calls:
```python
DEMO_MODE = True  # In triage_bot.py or triage_bot_advanced.py
```

This provides mock AI responses so you can test the entire pipeline offline.

## API Quota Information

**Free Tier Limits:**
- Requests per minute: Limited
- Requests per day: Limited
- Input tokens: Limited

**Current Status:** Quota exceeded. Quota will reset daily at UTC midnight.

**If You Hit Quota:**
1. Enable DEMO_MODE to test offline
2. Wait for quota reset
3. Upgrade to paid tier for production use

## Advanced Configuration

### Customize AI Prompts
Edit the prompt in `analyze_log()` function:
```python
response = model.generate_content(
    f"""You are an expert QA Engineer. Analyze this error log...
    {error_text}"""
)
```

### Change Model
Update the model name:
```python
model = genai.GenerativeModel('gemini-2.0-flash')  # or other available models
```

### Filter Report Output
Modify `generate_html_report()` to customize styling or add more sections.

## Troubleshooting

### Missing Dependencies
```bash
pip install -r requirements.txt
```

### Image Processing Issues
Ensure PIL is installed: `pip install pillow`

### API Errors
- Check API key validity
- Verify network connection
- Check quota status
- Enable DEMO_MODE for testing

### Encoding Issues (Windows)
The script automatically handles UTF-8 encoding on Windows.

## Next Steps

### To Make It Production-Ready:
1. Add database logging
2. Implement scheduling (cron/Windows Task Scheduler)
3. Add email notifications
4. Create dashboard for report viewing
5. Implement ticket creation (Jira/GitHub)
6. Add team collaboration features

### Example Integration:
```python
# Automatically run daily at 9 AM
from schedule import every, run_pending
import time

every().day.at("09:00").do(run_triage)

while True:
    run_pending()
    time.sleep(60)
```

## API Key Security

⚠️ **Important:** The API key is currently visible in the code. For production:
1. Use environment variables: `GEMINI_API_KEY=your_key python script.py`
2. Use config files (git-ignored)
3. Use secrets management (AWS Secrets Manager, etc.)

## Performance Notes

- First run: ~3-5 seconds (API call time)
- Subsequent runs: Faster if using demo mode
- Image processing: ~2-3 seconds
- Report generation: ~1 second

## Support & FAQ

**Q: Can I use a different AI model?**
A: Yes, replace `gemini-2.0-flash` with other available Gemini models.

**Q: How do I analyze multiple log files?**
A: Modify the script to loop through all `.txt` files in the `logs/` directory.

**Q: Can I integrate with CI/CD?**
A: Yes! Add as a post-test step in your pipeline.

## Version History

- **v1.0** (Current): Basic functionality + Advanced version
  - Log analysis
  - Image analysis  
  - HTML/JSON reports
  - Confidence scoring

## License

MIT - Free to use and modify

---

**Built with:** Python 3.12, Google Gemini API, Pillow  
**Last Updated:** December 2025
