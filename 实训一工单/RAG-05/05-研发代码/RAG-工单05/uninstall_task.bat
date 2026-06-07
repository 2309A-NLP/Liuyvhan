@echo off
chcp 65001 > nul
echo 正在移除 RAG Server 计划任务...
schtasks /DELETE /TN "RAG-Server-8001" /F
if %ERRORLEVEL% EQU 0 (
    echo 已移除。
) else (
    echo 移除失败或任务不存在。
)
pause
