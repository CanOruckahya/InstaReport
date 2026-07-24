@echo off
setlocal

python --version >nul 2>&1
if %errorlevel% NEQ 0 (
    echo [!] Python bulunamadi. Lutfen Python 3 kurun.
    pause
    exit /b 1
)

echo [+] Paketler yukleniyor...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo [>] Web uygulamasi baslatiliyor: http://127.0.0.1:5000
python app.py
pause
