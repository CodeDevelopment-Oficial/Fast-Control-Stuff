r"""Entrypoint WSGI para producción (pywina/Helicon con IIS).

Comando del handler de IIS (ejemplo):
  C:\venvs\flask\Scripts\python.exe C:\app\apps\flask_client\wsgi.py
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app import create_app  # noqa: E402

application = create_app()
app = application  # alias por convención (gunicorn --module wsgi:app)

if __name__ == "__main__":
    application.run()
