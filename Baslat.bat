@echo off
cd /d "%~dp0"
chcp 65001 >nul

python --version >nul 2>&1
if %errorlevel% NEQ 0 (
    echo [!] Python kurulu degil veya PATH'e eklenmemis.
    echo [*] Otomatik kurulum icin setup_launcher.bat dosyasini calistirabilirsiniz.
    pause
    exit /b 1
)

python -c "import bs4, matplotlib, PIL, tkinter" >nul 2>&1
if %errorlevel% NEQ 0 (
    echo [+] Eksik kutuphaneler kuruluyor...
    python -m pip install -r requirements.txt
    if %errorlevel% NEQ 0 (
        echo [!] Kutuphaneler kurulurken hata olustu.
        pause
        exit /b 1
    )
)

where pythonw >nul 2>&1
if %errorlevel% EQU 0 (
    start "" pythonw "%~dp0app.py"
) else (
    python "%~dp0app.py"
    if %errorlevel% NEQ 0 pause
)
