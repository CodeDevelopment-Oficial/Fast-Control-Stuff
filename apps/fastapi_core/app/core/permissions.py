"""Catálogo de permisos RBAC granulares: `recurso:acción`.

Se usa tanto en FastAPI (dependencias de endpoint) como en Flask (menús/botones).
Para agregar un módulo nuevo basta con añadir sus acciones aquí y correr el seed.
"""

RESOURCES = {
    "dashboard": ["view"],
    "usuarios": ["view", "create", "update", "delete", "export"],
    "roles": ["view", "create", "update", "delete"],
    "permisos": ["view", "assign"],
    "inventario": ["view", "create", "update", "delete", "export"],
    "herramientas": ["view", "create", "update", "delete", "export"],
    "rentals": ["view", "create", "update", "delete", "export"],
    "mantenimientos": ["view", "create", "update", "delete"],
    "certificaciones": ["view", "create", "update", "delete"],
    "auditoria": ["view", "export"],
}

# Superpoder reservado para super_admin: implícito sobre todo recurso:acción
PERMISSION_WILDCARD = "*:*"


def all_permissions() -> list[str]:
    perms = [f"{res}:{act}" for res, acts in RESOURCES.items() for act in acts]
    return sorted(perms + [PERMISSION_WILDCARD])
