@echo off
chcp 65001 > nul
echo Installing RAG Server auto-start task...
schtasks /CREATE /SC ONLOGON /TN "RAG-Server-8001" /TR "C:\Users\刘禹含\Desktop\RAG-工单04\start_server_loop.bat" /DELAY 0000:30 /IT /RL HIGHEST /F
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS: Task created. RAG Server will auto-start on next login.
) else (
    echo FAILED. Try running as Administrator (right-click - Run as administrator).
)
pause
