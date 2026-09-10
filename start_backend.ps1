Write-Host "===================================================================" -ForegroundColor Green
Write-Host "                    AYURCASE BACKEND SERVER                        " -ForegroundColor Green
Write-Host "===================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Starting Flask backend connected to SQLite database..." -ForegroundColor Yellow
Write-Host "Backend URL: http://127.0.0.1:5000" -ForegroundColor Cyan
Write-Host "Database: backend/ayurcase.db" -ForegroundColor Cyan
Write-Host ""
Write-Host "Leave this terminal window OPEN while browsing the website." -ForegroundColor Yellow
Write-Host "To stop the server, press Ctrl + C." -ForegroundColor Yellow
Write-Host ""

Set-Location -Path 

if (Test-Path ".\venv\Scripts\python.exe") {
    & ".\venv\Scripts\python.exe" "backend\app.py"
} else {
    python "backend\app.py"
}
