"""Seed: catálogo de permisos RBAC + rol super_admin + usuario administrador.

Uso:  python -m app.seed            (idempotente)
      FCS_ADMIN_EMAIL=... FCS_ADMIN_PASSWORD=... python -m app.seed
"""
import os

from app.core.database import SessionLocal
from app.core.permissions import PERMISSION_WILDCARD, all_permissions
from app.core.security import hash_password
from app.models.associations import user_roles
from app.models.user import Permission, Role, RolePermission, User

DEFAULT_ADMIN_EMAIL = "admin@fastcontrol.com"
DEFAULT_ADMIN_PASSWORD = "Admin#2026!"
DEFAULT_ADMIN_NAME = "Administrador General"


def run():
    # Crear esquema si no existe (desarrollo sin MySQL; en prod se usa Alembic)
    import app.models  # noqa: F401  (registra todos los modelos en Base.metadata)
    from app.core.database import Base, engine
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 1) Catálogo maestro de permisos recurso:acción
        existing = {p.code for p in db.query(Permission).all()}
        for code in all_permissions():
            if code not in existing:
                resource, action = (code.split(":") + [None])[:2]
                db.add(Permission(code=code, resource=resource, action=action,
                                  description=f"{action} sobre {resource}" if code != PERMISSION_WILDCARD else "Acceso total"))
        db.flush()

        # 2) Rol super_admin con el comodín *:* (resuelto en runtime a todos los permisos)
        role = db.query(Role).filter(Role.name == "super_admin").one_or_none()
        if role is None:
            role = Role(name="super_admin", description="Acceso total al sistema")
            db.add(role)
            db.flush()

        wildcard = db.query(Permission).filter(Permission.code == PERMISSION_WILDCARD).one()
        has_wildcard = db.query(RolePermission).filter_by(role_id=role.id, permission_id=wildcard.id).one_or_none()
        if has_wildcard is None:
            db.add(RolePermission(role_id=role.id, permission_id=wildcard.id, effect="grant"))

        # 3) Usuario administrador inicial
        email = os.getenv("FCS_ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL).lower()
        password = os.getenv("FCS_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            user = User(
                email=email,
                full_name=os.getenv("FCS_ADMIN_NAME", DEFAULT_ADMIN_NAME),
                password_hash=hash_password(password),
                is_active=True,
            )
            db.add(user)
            db.flush()
            db.execute(user_roles.insert().values(user_id=user.id, role_id=role.id))
            print(f"[seed] Usuario creado: {email}")
            print("[seed] ⚠️  Cambia esta contraseña en producción.")
        else:
            print(f"[seed] Usuario ya existe: {email}")

        db.commit()
        print("[seed] OK — permisos, rol super_admin y administrador listos.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
