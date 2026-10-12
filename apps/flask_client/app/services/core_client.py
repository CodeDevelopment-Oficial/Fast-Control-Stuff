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

    def _request(self, method: str, path: str, *, json_body=None, token: str | None = None):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            resp = self.session.request(method, f"{self.base}{path}", json=json_body,
                                        headers=headers, timeout=self.timeout)
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
