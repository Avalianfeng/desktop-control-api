@echo off
chcp 65001 >nul
echo.
echo ╔══════════════════════════════════════════╗
echo ║     Desktop Control API Server           ║
echo ║     为 AI 代理提供的桌面自动化服务              ║
echo ╚══════════════════════════════════════════╝
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

REM 检查依赖
echo [检查] 验证依赖包...
python -c "import fastapi, uvicorn, pyautogui, mss, PIL, cv2" >nul 2>&1
if errorlevel 1 (
    echo [安装] 正在安装依赖包...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
)

echo.
echo [启动] 正在启动服务器...
echo.
echo 服务地址：http://127.0.0.1:8765
echo API 文档：http://127.0.0.1:8765/docs
echo API Key: desktop-control-key
echo.
echo 按 Ctrl+C 停止服务
echo.

python server.py
