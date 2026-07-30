@echo off
setlocal

:: Python kurulu mu kontrol et
python --version >nul 2>&1
if %errorlevel% NEQ 0 (
    echo [!] Python bulunamadı. Indiriliyor...
    curl -o python-installer.exe https://www.python.org/ftp/python/3.10.10/python-3.10.10-amd64.exe

    echo [*] Python sessiz kuruluyor...
    start /wait python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    del python-installer.exe

    echo [*] Python kuruldu, terminale tekrar erisiliyor...
    refreshenv
)

:: pip'i güncelle ve gerekli paketleri kur
echo [+] Paketler yükleniyor...
python -m pip install --upgrade pip
python -m pip install beautifulsoup4 matplotlib pillow

:: Uygulama başlatılıyor
echo [>] Uygulama başlatılıyor...
python app.py

pause
