@echo off
chcp 65001 >nul
pushd C:\Users\刘禹含\Desktop\RAG-工单05
echo === Python 进程 ===
tasklist /FI "IMAGENAME eq python.exe" /FO TABLE 2>nul
echo.
echo === 端口 8001 ===
netstat -ano | findstr ":8001"
echo.
echo === 端口 19530 ===
netstat -ano | findstr ":19530"
echo.
echo === 端口 6379 ===
netstat -ano | findstr ":6379"
echo.
popd
