@echo off
call synenv\Scripts\activate
python -m playwright install chromium
npm exec playwright install chromium
pause
