@echo off
chcp 65001 >nul
title Embedding微调 - 数据生成

echo ============================================
echo   Step 1: 生成训练数据 (Q&A对)
echo ============================================
echo.
echo 正在启动 LLM 问答对生成...
echo (请确保 .env 中的 LLM_API_KEY 是有效的)
echo.

pushd "%~dp0.."
D:\Anaconda\envs\RAG\python.exe scripts\generate_qa_pairs.py --limit 200

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [错误] 脚本执行失败，请检查 API Key 和环境配置
    pause
    exit /b 1
)

echo.
echo 数据生成完成！
echo 请检查 data/processed/finetune_triplets.json
pause
