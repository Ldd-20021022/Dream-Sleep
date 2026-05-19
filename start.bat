@echo off
chcp 65001 >nul
echo ================================
echo   梦眠 - 后端服务启动
echo ================================

cd /d "%~dp0backend"

echo.
echo [1/2] 检查依赖...
pip install -r requirements.txt -q 2>nul
echo 依赖就绪

echo [2/2] 启动服务...
echo.
echo   本地访问: http://127.0.0.1:8000
echo   局域网:   http://192.168.3.64:8000
echo   API文档:  http://127.0.0.1:8000/docs
echo.
echo ================================

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
