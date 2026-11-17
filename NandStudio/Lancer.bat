@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 goto python
py -3 app.py
goto done
:python
python3 app.py
:done
if errorlevel 1 (
echo Installez Python 3.10+ et Pillow : python -m pip install -r requirements.txt
pause
)
