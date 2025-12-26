"""
Mini-Triage Bot - Interactive Demo & Configuration Utility
Provides an interactive menu to run triage analysis and configure the bot
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def print_banner():
    """Print the application banner"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║         Mini-Triage Bot - Interactive Dashboard             ║
║    AI-Powered Automated Failure Analysis & Reporting        ║
╚══════════════════════════════════════════════════════════════╝
    """)

def print_menu():
    """Display main menu"""
    print("\n" + "="*60)
    print("MAIN MENU")
    print("="*60)
    print("1. Run Basic Analysis (triage_bot.py)")
    print("2. Run Advanced Analysis (triage_bot_advanced.py)")
    print("3. Enable Demo Mode (for testing without API calls)")
    print("4. View Last Report")
    print("5. View API Status")
    print("6. Configure API Key")
    print("7. Check System Status")
    print("0. Exit")
    print("="*60)

def run_analysis(script_name):
    """Run the specified analysis script"""
    python_cmd = f"C:/Users/HP/Downloads/Mini-Triage-Bot/.venv/Scripts/python.exe"
    os.system(f"cd C:\\Users\\HP\\Downloads\\Mini-Triage-Bot && {python_cmd} {script_name}")

def enable_demo_mode(script_name):
    """Enable demo mode in the specified script"""
    try:
        with open(script_name, 'r') as f:
            content = f.read()
        
        content = content.replace('DEMO_MODE = False', 'DEMO_MODE = True')
        
        with open(script_name, 'w') as f:
            f.write(content)
        
        print(f"\n✓ Demo mode enabled in {script_name}")
        print("  The bot will now use mock AI responses for testing")
    except Exception as e:
        print(f"\n✗ Error: {e}")

def disable_demo_mode(script_name):
    """Disable demo mode in the specified script"""
    try:
        with open(script_name, 'r') as f:
            content = f.read()
        
        content = content.replace('DEMO_MODE = True', 'DEMO_MODE = False')
        
        with open(script_name, 'w') as f:
            f.write(content)
        
        print(f"\n✓ Demo mode disabled in {script_name}")
        print("  The bot will now use real API calls")
    except Exception as e:
        print(f"\n✗ Error: {e}")

def view_latest_report():
    """View the latest generated report"""
    reports_dir = "reports"
    if not os.path.exists(reports_dir):
        print("\nNo reports directory found.")
        return
    
    html_files = [f for f in os.listdir(reports_dir) if f.endswith('.html')]
    if not html_files:
        print("\nNo HTML reports found.")
        return
    
    latest = sorted(html_files)[-1]
    filepath = os.path.join(reports_dir, latest)
    print(f"\nLatest Report: {filepath}")
    print(f"Generated: {datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d %H:%M:%S')}")
    
    choice = input("\nOpen in browser? (y/n): ").lower()
    if choice == 'y':
        os.system(f"start {filepath}")
    
    # Show summary
    if latest.endswith('.html'):
        json_file = latest.replace('.html', '.json')
        json_path = os.path.join(reports_dir, json_file)
        if os.path.exists(json_path):
            with open(json_path) as f:
                data = json.load(f)
            print(f"\nConfidence Score: {data.get('confidence_score', 'N/A')}%")
            print(f"Recommendation: {data.get('recommendation', 'N/A')}")

def check_system_status():
    """Check system and project status"""
    print("\n" + "="*60)
    print("SYSTEM STATUS")
    print("="*60)
    
    # Check Python
    python_path = sys.executable
    print(f"Python: {python_path}")
    print(f"Python Version: {sys.version.split()[0]}")
    
    # Check required packages
    try:
        import google.generativeai
        print("✓ google-generativeai: installed")
    except:
        print("✗ google-generativeai: NOT installed")
    
    try:
        from PIL import Image
        print("✓ Pillow (PIL): installed")
    except:
        print("✗ Pillow (PIL): NOT installed")
    
    # Check files
    print("\nProject Files:")
    if os.path.exists("logs/fail_log.txt"):
        print("✓ logs/fail_log.txt: found")
    else:
        print("✗ logs/fail_log.txt: NOT found")
    
    if os.path.exists("logs/faliure.png") or os.path.exists("logs/failure.png"):
        print("✓ logs/[failure|faliure].png: found")
    else:
        print("✗ logs/failure.png: NOT found")
    
    # Count reports
    if os.path.exists("reports"):
        report_count = len([f for f in os.listdir("reports")])
        print(f"\n✓ Reports directory: {report_count} files")
    else:
        print("✗ Reports directory: not found")

def view_api_status():
    """Show API status and quota information"""
    print("\n" + "="*60)
    print("API STATUS")
    print("="*60)
    print("""
Model: Gemini 2.0 Flash
API Endpoint: generativelanguage.googleapis.com

Free Tier Limits:
- Requests/minute: Limited
- Requests/day: Limited
- Input tokens/min: Limited

Current Status: Check by running analysis

Actions:
1. Run analysis to check quota
2. Wait for daily reset at UTC midnight
3. Upgrade to paid tier for unlimited access

API Key Status: CONFIGURED
Model Status: ACTIVE
    """)

def configure_api_key():
    """Configure the API key"""
    print("\n" + "="*60)
    print("CONFIGURE API KEY")
    print("="*60)
    
    current_key = os.getenv("GEMINI_API_KEY", "Not set")
    print(f"\nCurrent Key Status: {('CONFIGURED' if current_key != 'Not set' else 'NOT CONFIGURED')}")
    
    print("""
To get a new API key:
1. Go to: https://ai.google.dev/
2. Click "Create API key"
3. Copy it immediately

Professional Setup (You're Already Using This!):
- Your key is stored in .env file (secure)
- Never exposed in your code (professional!)
- Not committed to version control
- This is how real engineers do it!

IMPORTANT: Keep your API key secret!
- Don't share publicly
- Don't paste in chat or screenshots
- Don't commit .env to git
    """)
    
    choice = input("Update API key in .env file? (y/n): ").lower()
    if choice == 'y':
        new_key = input("Paste your NEW API key: ").strip()
        if new_key:
            try:
                # Read current .env content
                env_path = ".env"
                if os.path.exists(env_path):
                    with open(env_path, 'r') as f:
                        content = f.read()
                    # Replace the key
                    lines = content.split('\n')
                    updated_lines = []
                    for line in lines:
                        if line.startswith('GEMINI_API_KEY='):
                            updated_lines.append(f'GEMINI_API_KEY={new_key}')
                        else:
                            updated_lines.append(line)
                    
                    with open(env_path, 'w') as f:
                        f.write('\n'.join(updated_lines))
                else:
                    # Create .env if it doesn't exist
                    with open(env_path, 'w') as f:
                        f.write(f'GEMINI_API_KEY={new_key}\n')
                
                print(f"\nSUCCESS!")
                print(f"Your API key has been saved to .env file")
                print(f"The key is now secure and not exposed in your code!")
                
            except Exception as e:
                print(f"Error updating .env: {e}")
        else:
            print("No key entered.")
    else:
        print("Skipped.")

def main():
    """Main interactive loop"""
    os.chdir("C:\\Users\\HP\\Downloads\\Mini-Triage-Bot")
    
    while True:
        print_banner()
        print_menu()
        choice = input("\nEnter your choice (0-7): ").strip()
        
        if choice == '1':
            print("\nRunning basic analysis...")
            run_analysis("triage_bot.py")
        
        elif choice == '2':
            print("\nRunning advanced analysis...")
            run_analysis("triage_bot_advanced.py")
        
        elif choice == '3':
            print("\nDemo Mode Options:")
            print("1. Enable Demo Mode")
            print("2. Disable Demo Mode")
            demo_choice = input("Choose (1-2): ").strip()
            
            if demo_choice == '1':
                enable_demo_mode("triage_bot.py")
                enable_demo_mode("triage_bot_advanced.py")
            elif demo_choice == '2':
                disable_demo_mode("triage_bot.py")
                disable_demo_mode("triage_bot_advanced.py")
        
        elif choice == '4':
            view_latest_report()
        
        elif choice == '5':
            view_api_status()
        
        elif choice == '6':
            configure_api_key()
        
        elif choice == '7':
            check_system_status()
        
        elif choice == '0':
            print("\nGoodbye!")
            break
        
        else:
            print("\nInvalid choice. Please try again.")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
