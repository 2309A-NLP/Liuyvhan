@echo off
chcp 65001 >nul
title Embedding微调 - 训练

echo ============================================
echo   Step 2: 微调 Embedding 模型
echo ============================================
echo.
echo  基准模型: BAAI/bge-base-zh-v1.5
echo  训练数据: data/processed/finetune_triplets.json
echo  输出路径: data/models/finetuned-bge-zh/
echo.
echo [注意] 首次运行会从 HuggingFace 下载模型
echo        请确保网络连接正常
echo.

pushd "%~dp0.."
D:\Anaconda\envs\RAG\python.exe scripts\finetune_embedding.py --epochs 3 --batch-size 8

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [错误] 微调失败，请查看上方错误信息
    pause
    exit /b 1
)

echo.
echo ============================================
echo   微调完成！接下来操作：
echo   1. 修改 .env 的 EMBEDDING_MODEL_PATH
echo      指向 data/models/finetuned-bge-zh/
echo   2. 重启服务
echo   3. 重新索引 PDF
echo   4. 跑评估对比
echo ============================================
echo.
pause
