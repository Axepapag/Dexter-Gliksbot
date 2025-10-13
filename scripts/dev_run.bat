@echo off
call .venv\Scripts\activate
uvicorn dexter_autonomy.ui_bridge.api:app --host 127.0.0.1 --port 8765 --reload
