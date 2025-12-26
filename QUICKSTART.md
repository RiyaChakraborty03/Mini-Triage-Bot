# Quick Start Guide - Mini-Triage Bot

## 🚀 Get Started in 60 Seconds

### Step 1: Run the Bot
Open PowerShell and run:
```powershell
cd C:\Users\HP\Downloads\Mini-Triage-Bot
.\venv\Scripts\python.exe triage_bot.py
```

### Step 2: View the Report
Open the generated HTML report:
```
C:\Users\HP\Downloads\Mini-Triage-Bot\triage_report.html
```

### Step 3: Try Advanced Features
```powershell
.\venv\Scripts\python.exe triage_bot_advanced.py
```

This generates reports in the `reports/` folder with:
- Beautiful HTML with confidence scores
- Structured JSON data
- Timestamped analysis

---

## 📊 What You Just Did

Your bot:
1. ✅ Read the error log (`logs/fail_log.txt`)
2. ✅ Analyzed the failure screenshot (`logs/faliure.png`)
3. ✅ Used Google Gemini AI to understand the failures
4. ✅ Generated professional reports with confidence scores
5. ✅ Automated the entire triage process

---

## 🎮 Interactive Dashboard

Run the interactive launcher for a user-friendly menu:
```powershell
.\venv\Scripts\python.exe launcher.py
```

Features:
- Run analysis with one click
- Enable/disable demo mode
- View past reports
- Check API status
- Configure settings

---

## 🔧 Key Features

### Basic Analysis (`triage_bot.py`)
- Log file reading and analysis
- Screenshot processing
- Single HTML report
- Simple and fast

### Advanced Analysis (`triage_bot_advanced.py`)
- Multi-format reports (HTML + JSON)
- Confidence scoring
- Timestamped outputs
- Structured data export
- Better error handling

### Demo Mode
Test the entire bot without using API quota:
```python
# In triage_bot.py or triage_bot_advanced.py:
DEMO_MODE = True  # Set to True for mock analysis
```

---

## 📁 Project Structure

```
Mini-Triage-Bot/
├── triage_bot.py              (main script)
├── triage_bot_advanced.py     (advanced version)
├── launcher.py                (interactive menu)
├── README.md                  (full documentation)
├── QUICKSTART.md              (this file)
├── logs/
│   ├── fail_log.txt           (your error log)
│   └── faliure.png            (failure screenshot)
└── reports/
    ├── report_*.html          (generated reports)
    └── report_*.json          (structured data)
```

---

## 🎯 Common Tasks

### Run Basic Analysis
```bash
python triage_bot.py
```
Output: `triage_report.html`

### Run Advanced Analysis  
```bash
python triage_bot_advanced.py
```
Output: `reports/report_*.html` + `reports/report_*.json`

### Test Offline (Demo Mode)
```python
DEMO_MODE = True
python triage_bot.py
```

### Change Error Log
Edit `logs/fail_log.txt` or update the path in the script:
```python
LOG_PATH = "logs/your_log.txt"
```

### Add New Screenshot
Replace `logs/faliure.png` or update the path:
```python
IMAGE_PATH = "logs/your_screenshot.png"
```

---

## ⚠️ Important Notes

### API Quota
- Free tier has daily limits
- If you hit the limit: Wait for reset or enable DEMO_MODE
- Upgrade to paid for production use

### API Key Security
- Your key is configured in the scripts
- For production: Use environment variables
- Never commit keys to version control

### Encoding (Windows)
- Script handles UTF-8 automatically
- If you see encoding errors, the fix is already included

---

## 🆘 Troubleshooting

### "Module not found" Error
Install dependencies:
```bash
pip install google-generativeai pillow
```

### "File not found" Error  
Check that these files exist:
- `logs/fail_log.txt` ✓
- `logs/faliure.png` ✓

### "Quota exceeded" Error
Either:
1. Enable DEMO_MODE = True
2. Wait for daily quota reset
3. Upgrade to paid API tier

### "Encoding error" (Windows)
Already fixed in the code. If persists:
```python
import sys
sys.stdout.encoding = 'utf-8'
```

---

## 🎓 Learning Path

### Day 1-2: Setup ✓
- Python environment ready
- Dependencies installed
- API key configured

### Day 3-4: File Reading ✓
- Run `triage_bot.py`
- Verify it reads `fail_log.txt`

### Day 5-6: AI Integration ✓
- Script uses Gemini API
- Analyzes text automatically

### Day 7-8: Vision AI ✓
- Screenshots processed
- Multi-modal analysis works

### Day 9: Reporting ✓
- HTML reports generated
- JSON structured data created
- Confidence scoring included

### Day 10: Demo Ready ✓
- Full pipeline automated
- Reusable bot created
- Easy to extend

---

## 🚀 Next Steps

### For Local Use
- Customize prompts in the scripts
- Add more test cases
- Experiment with different failure types

### For Production
- Store API key in environment variable
- Add database logging
- Create web dashboard
- Set up CI/CD integration
- Add email notifications

### For Distribution
- Package as executable
- Create GUI with tkinter
- Build Docker container
- Publish on GitHub

---

## 📞 Support

For help:
1. Check README.md (full documentation)
2. Enable DEMO_MODE to test offline
3. Check your error logs in detail
4. Verify all files are in place

---

## 🎉 You're All Set!

Your Mini-Triage Bot is:
- ✅ Installed
- ✅ Configured  
- ✅ Tested
- ✅ Ready to use

**Next: Run `python triage_bot.py` and see it analyze your logs!**

---

*Last Updated: December 26, 2025*  
*Version: 1.0 - MVP Ready*
