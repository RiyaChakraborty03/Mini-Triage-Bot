from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
import os
import shutil
from datetime import datetime
from triage_bot_advanced import run_triage, batch_analyze_logs, call_cody_api, health_check_api

app = FastAPI(title="NXP AI Triage Bot API")

# Ensure folders exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("logs", exist_ok=True)
os.makedirs("reports", exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with basic HTML information"""
    return """
    <html>
        <head>
            <title>NXP AI Triage Bot API</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
                       line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }
                h1 { color: #0066cc; }
                .card { background: #f9f9f9; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .endpoint { background: #e6f3ff; padding: 10px; border-left: 4px solid #0066cc; margin: 10px 0; }
                a { color: #0066cc; text-decoration: none; }
                a:hover { text-decoration: underline; }
            </style>
        </head>
        <body>
            <h1>NXP AI Triage Bot API</h1>
            <p>Automate regression log analysis with AI-powered triage.</p>
            
            <div class="card">
                <h2>API Documentation</h2>
                <p>Visit <a href='/docs'>/docs</a> for the Swagger UI documentation.</p>
            </div>
            
            <div class="card">
                <h2>Available Endpoints</h2>
                <div class="endpoint"><strong>GET /health</strong> - Check API health including AI service</div>
                <div class="endpoint"><strong>POST /analyze/upload</strong> - Upload and analyze a log file</div>
                <div class="endpoint"><strong>GET /analyze/batch</strong> - Analyze all logs in the logs directory</div>
                <div class="endpoint"><strong>GET /reports/{report_name}</strong> - View generated reports</div>
            </div>
        </body>
    </html>
    """

@app.post("/analyze/upload")
async def analyze_upload(log_file: UploadFile = File(...), image_file: UploadFile = None, background_tasks: BackgroundTasks = None):
    """Upload and analyze a log file with optional screenshot"""
    try:
        # 1. Save uploaded files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{timestamp}_{log_file.filename}"
        log_path = f"uploads/{log_filename}"
        
        with open(log_path, "wb") as buffer:
            shutil.copyfileobj(log_file.file, buffer)
        
        # Also save a copy to the logs directory for batch processing
        logs_copy_path = f"logs/{log_filename}"
        shutil.copy(log_path, logs_copy_path)
            
        # Handle optional image file
        img_path = None
        if image_file:
            img_filename = f"{timestamp}_{image_file.filename}"
            img_path = f"uploads/{img_filename}"
            with open(img_path, "wb") as buffer:
                shutil.copyfileobj(image_file.file, buffer)
            
            # Also save to logs directory
            img_logs_path = f"logs/{img_filename}"
            shutil.copy(img_path, img_logs_path)

        # 2. Run triage analysis
        result = run_triage(log_file=log_path, image_file=img_path)
        
        if not result or result.get('status') == 'failed':
            raise HTTPException(status_code=500, detail="Analysis failed")
            
        # 3. Return the results
        return {
            "status": "success",
            "analysis": {
                "severity": result.get('severity'),
                "confidence": result.get('confidence'),
                "priority": result.get('priority'),
                "categories": result.get('categories')
            },
            "reports": {
                "html": f"/reports/{os.path.basename(result['html_report'])}",
                "json": f"/reports/{os.path.basename(result['json_report'])}"
            },
            "files": {
                "log": log_path,
                "image": img_path
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing upload: {str(e)}")

@app.get("/analyze/batch")
async def trigger_batch(background_tasks: BackgroundTasks = None):
    """Trigger a batch analysis of all logs in the logs directory"""
    try:
        # Option to run in background
        if background_tasks:
            background_tasks.add_task(batch_analyze_logs)
            return {"status": "batch_analysis_started", "message": "Batch analysis started in background"}
        
        # Run synchronously
        results = batch_analyze_logs()
        
        # Extract just the key information for the summary
        summary_results = []
        for result in results:
            summary_results.append({
                "log_file": os.path.basename(result.get('log_file', 'unknown')),
                "severity": result.get('severity', 'Unknown'),
                "confidence": result.get('confidence', 0),
                "priority": result.get('priority', 'Unknown'),
                "categories": result.get('categories', []),
                "reports": {
                    "html": f"/reports/{os.path.basename(result.get('html_report', ''))}",
                    "json": f"/reports/{os.path.basename(result.get('json_report', ''))}"
                }
            })
        
        return {
            "status": "batch_complete", 
            "count": len(results), 
            "summary_report": f"/reports/batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            "results": summary_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch analysis error: {str(e)}")

@app.get("/reports/{report_name}")
async def get_report(report_name: str):
    """Retrieve a generated report by name"""
    report_path = f"reports/{report_name}"
    if os.path.exists(report_path):
        return FileResponse(report_path)
    return {"error": "Report not found"}

@app.get("/uploads/{file_name}")
async def get_uploaded_file(file_name: str):
    """Retrieve an uploaded file"""
    file_path = f"uploads/{file_name}"
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return {"error": "File not found"}

@app.get("/health")
async def health_check():
    """Health check endpoint to verify API connectivity"""
    try:
        # Simple, lightweight prompt to test the API
        test_prompt = "Respond with 'API is operational' if you receive this message."
        
        # Set a shorter timeout for health checks
        response = call_cody_api(test_prompt, retry_count=0)  # No retries for health check
        
        # Check if we got a valid response
        if response and len(response) > 5 and "error" not in response.lower():
            return {
                "status": "healthy",
                "api": "cody_api",
                "mode": "LIVE",
                "message": "API is operational and responding"
            }
        else:
            return {
                "status": "degraded",
                "api": "cody_api", 
                "mode": "LIVE",
                "message": f"API returned unexpected response: {response[:50]}...",
                "error": "Invalid response format"
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "api": "cody_api",
            "mode": "LIVE",
            "message": "API health check failed",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    import sys
    
    if "--reload" in sys.argv:
        uvicorn.run("main:app", host="localhost", port=8000, reload=True)
    else:
        uvicorn.run(app, host="localhost", port=8000)
