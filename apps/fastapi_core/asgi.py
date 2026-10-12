"""Entrypoint ASGI para producción (uvicorn con IIS como reverse proxy).

Comandos válidos desde apps/fastapi_core:
  uvicorn asgi:app --host 127.0.0.1 --port 8000
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000   (requiere cwd aquí)
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.main import app  # noqa: E402

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
