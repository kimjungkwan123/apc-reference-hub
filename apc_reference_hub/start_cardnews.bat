@echo off
set PORT=8512
start http://127.0.0.1:%PORT%
streamlit run cardnews_app.py --server.headless true --server.address 0.0.0.0 --server.port %PORT% --browser.gatherUsageStats false
