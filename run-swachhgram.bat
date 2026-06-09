@echo off
title SwachhGram Project Startup
echo ========================================
echo       SwachhGram Waste Management
echo ========================================
echo.
echo Starting all services...
echo.

echo [1/5] Starting Shared Data Server...
start "Shared Data Server" cmd /k "cd /d %~dp0 && python shared-data-server.py"
timeout /t 3 >nul

echo [2/5] Starting Auth Service...
start "Auth Service" cmd /k "cd /d %~dp0auth_service && python test_main_fixed_v3.py"
timeout /t 3 >nul

echo [3/5] Starting Citizen App...
start "Citizen App" cmd /k "cd /d %~dp0citizen-app && python -m http.server 3001"
timeout /t 3 >nul

echo [4/5] Starting Crew App...
start "Crew App" cmd /k "cd /d %~dp0crew-app && python -m http.server 3002"
timeout /t 3 >nul

echo [5/5] Starting Admin Dashboard...
start "Admin Dashboard" cmd /k "cd /d %~dp0admin-dashboard && python -m http.server 3003"
timeout /t 3 >nul

echo.
echo ========================================
echo      All Services Started!
echo ========================================
echo.
echo Access Portals:
echo   Citizen App:    http://localhost:3001
echo   Crew App:       http://localhost:3002
echo   Admin Dashboard: http://localhost:3003
echo.
echo Login Credentials:
echo   Citizen: citizen / cit123
echo   Crew:    crew / crew123
echo   Admin:    admin / admin123
echo.
echo Press any key to stop all services...
pause >nul

echo.
echo Stopping all services...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im cmd.exe >nul 2>&1
echo All services stopped.
pause
