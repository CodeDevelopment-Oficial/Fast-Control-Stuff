# Fast Control Stuff — Sistema de Control y Administración de Inventarios

Sistema web para una empresa del ramo petrolero dedicada a la **renta de herramientas de perforación de pozos**.

## Stack

| Componente        | Tecnología                                             |
|-------------------|--------------------------------------------------------|
| Frontend / MVC    | Python 3.11+, Flask, Jinja2 + Tailwind CSS (CDN)       |
| API core / BD     | FastAPI + SQLAlchemy 2.0 + Alembic                     |
| Base de datos     | MySQL 8.x                                              |
| Autenticación     | Sesiones HTTP-only en Flask + JWT/Refresh emitidos por FastAPI |
| Hashing           | Argon2 con bloqueo por intentos fallidos               |
| Correo            | SMTP propio (recuperación de contraseña)               |
| Despliegue        | IIS como reverse proxy (subdominios o puertos internos)|

## Arquitectura

- **FastAPI es el único dueño de la base de datos.** Flask nunca se conecta a MySQL;
  todo acceso a datos pasa por la API interna (`/api/v1/*`).
- **MVC en Flask**: `routes` (controladores), `templates` (vistas), servicios que actúan
  de modelo consumiendo la API.
- **RBAC granular**: permisos por `recurso:acción` (p. ej. `inventario:create`,
  `herramientas:export`) evaluados a nivel de botón/menu en Flask y de endpoint en FastAPI.
  Tabla puente `role_permissions` con `grant/deny` para privilegios finos.
- Rol inicial único: **super_admin** (todos los permisos). Nuevos roles se agregan sin
  cambiar el esquema.

```
workspace/
├── apps/
│   ├── flask_client/    # MVC, vistas, sesiones HTTP-only
│   └── fastapi_core/    # API, modelos SQLAlchemy, Alembic, JWT, RBAC, SMTP
├── database/
│   └── seeds/           # seed de permisos y super_admin
├── docs/
│   └── ARCHITECTURE.md
└── .env.example
```

## Puertos de desarrollo

| Servicio      | URL                          |
|---------------|------------------------------|
| Flask (login) | http://localhost:5000        |
| FastAPI (core)| http://localhost:8000 (docs en `/docs`) |

En producción IIS enruta `app.midominio.com -> :5000` y `api.midominio.com -> :8000`.

## Arranque rápido

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Configurar entorno
cp .env.example apps/fastapi_core/.env
cp .env.example apps/flask_client/.env

# 2. Migraciones + seed (permisos + usuario super_admin)
cd apps/fastapi_core
alembic upgrade head
python -m app.seed

# 3. Levantar FastAPI
uvicorn app.main:app --reload --port 8000

# 4. En otra terminal, levantar Flask
cd apps/flask_client
flask run --debug --port 5000
```

## Login (primera entrega)

Pantalla completa: mitad izquierda con nombre del sistema y beneficios; mitad derecha con
formulario de **inputs flotantes animados (CSS puro)**, botón de **recordar sesión** y enlace
de **¿Olvidaste tu contraseña?** (token por SMTP). Bloqueo de cuenta tras 5 intentos fallidos.

Credenciales semilla: `admin@fastcontrol.com` / `Admin#2026!` (cámbiala en producción).
