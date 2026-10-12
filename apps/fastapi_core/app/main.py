from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints import auth, tools
from app.core.config import settings
from app.core.errors import register_exception_handlers

app = FastAPI(
    title="Fast Control Stuff — Core API",
    description="API única dueña de la base de datos (MySQL). Inventario de herramientas de perforación.",
    version="0.1.0",
    docs_url="/docs",
)

# Solo el origen de Flask (interno); en producción ajustar con el subdominio interno.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=False,  # la API no maneja cookies del navegador
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

API_V1 = "/api/v1"
app.include_router(auth.router, prefix=API_V1)
app.include_router(tools.router, prefix=API_V1)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "service": "fastapi-core"}
