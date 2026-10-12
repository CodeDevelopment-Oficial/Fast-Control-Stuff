"""Modelo (en términos MVC): envoltorio del cliente HTTP hacia FastAPI core.

Flask nunca toca la BD; este servicio centraliza las llamadas a la API interna.
"""
from __future__ import annotations

import requests


class CoreError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


class CoreClient:
    def __init__(self, base_url: str, timeout: int = 10):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    # ------------------------------------------------------------ helpers

    def _request(self, method: str, path: str, *, json_body=None, token: str | None = None,
                 params: dict | None = None):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        clean_params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        try:
            resp = self.session.request(method, f"{self.base}{path}", json=json_body,
                                        headers=headers, params=clean_params or None,
                                        timeout=self.timeout)
        except requests.RequestException as exc:
            raise CoreError(503, "core_unreachable",
                            "No hay conexión con el servicio core. Intenta en unos momentos.") from exc

        if resp.status_code >= 400:
            detail = {}
            try:
                payload = resp.json()
                detail = payload.get("detail", {})
            except ValueError:
                pass
            if isinstance(detail, dict):
                code = detail.get("code", "api_error")
                message = detail.get("message", "Ocurrió un error inesperado.")
            else:
                code, message = "api_error", str(detail) or "Ocurrió un error inesperado."
            raise CoreError(resp.status_code, code, message)
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    # ------------------------------------------------------------ auth

    def login(self, email: str, password: str) -> dict:
        return self._request("POST", "/auth/login", json_body={"email": email, "password": password})

    def refresh(self, refresh_token: str) -> dict:
        return self._request("POST", "/auth/refresh", json_body={"refresh_token": refresh_token})

    def logout(self, refresh_token: str) -> None:
        self._request("POST", "/auth/logout", json_body={"refresh_token": refresh_token})

    def me(self, access_token: str) -> dict:
        return self._request("GET", "/auth/me", token=access_token)

    def forgot_password(self, email: str) -> dict:
        return self._request("POST", "/auth/forgot-password", json_body={"email": email})

    def reset_password(self, token: str, new_password: str) -> dict:
        return self._request("POST", "/auth/reset-password",
                             json_body={"token": token, "new_password": new_password})

    # ------------------------------------------------------------ herramientas

    def tools_list(self, token: str, params: dict | None = None) -> dict:
        return self._request("GET", "/tools", token=token, json_body=None, params=params)

    def tool_get(self, token: str, tool_id: int) -> dict:
        return self._request("GET", f"/tools/{tool_id}", token=token)

    def tool_create(self, token: str, body: dict) -> dict:
        return self._request("POST", "/tools", token=token, json_body=body)

    def tool_update(self, token: str, tool_id: int, body: dict) -> dict:
        return self._request("PATCH", f"/tools/{tool_id}", token=token, json_body=body)

    def tool_delete(self, token: str, tool_id: int) -> None:
        self._request("DELETE", f"/tools/{tool_id}", token=token)

    def tool_status(self, token: str, tool_id: int, status: str, reason: str) -> dict:
        return self._request("POST", f"/tools/{tool_id}/status", token=token,
                             json_body={"status": status, "reason": reason})

    def tool_hours(self, token: str, tool_id: int, hours: float, reason: str | None = None) -> dict:
        return self._request("POST", f"/tools/{tool_id}/hours", token=token,
                             json_body={"hours": hours, "reason": reason})

    def tool_move(self, token: str, tool_id: int, to_location_id: int, reason: str | None = None) -> dict:
        return self._request("POST", f"/tools/{tool_id}/move", token=token,
                             json_body={"to_location_id": to_location_id, "reason": reason})

    def categories(self, token: str) -> list:
        return self._request("GET", "/tools/categories", token=token)

    def types(self, token: str, category_id: int | None = None) -> list:
        params = {"category_id": category_id} if category_id else None
        return self._request("GET", "/tools/types", token=token, params=params)

    def locations(self, token: str) -> list:
        return self._request("GET", "/tools/locations", token=token)

    def counters(self, token: str) -> dict:
        return self._request("GET", "/tools/counters", token=token)
