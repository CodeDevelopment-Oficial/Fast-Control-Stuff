"""Garantiza que el paquete `app` sea importable sin importar el directorio
desde donde se invoquen herramientas (alembic, pytest, scripts).

Alembic carga env.py con exec() y NO añade el cwd a sys.path; este archivo
cubre ese caso cuando se ejecuta `alembic` desde apps/fastapi_core.
(Para otros casos existe el bootstrap de sys.path en alembic/env.py.)
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
