"""Atalho local: python run_api.py  (respeita STOCKFLOW_HOST/PORT/RELOAD)."""
import os
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "stockflow.api.main:app",
        host=os.getenv("STOCKFLOW_HOST", "127.0.0.1"),
        port=int(os.getenv("STOCKFLOW_PORT", "8000")),
        reload=os.getenv("STOCKFLOW_RELOAD", "1") == "1",
    )