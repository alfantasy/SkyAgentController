@echo off

echo Initializing virtual environment...

call venv\Scripts\activate.bat

echo Starting Sky Server controller...

fastapi dev --host 0.0.0.0 --port 7901
