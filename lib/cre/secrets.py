from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

from .cli import CRECLI, CRECommandResult
from .templates import secrets_delete_yaml, secrets_yaml, write_text


class CRESecrets:
    def __init__(self, *, root: str | Path = ".", cli: Optional[CRECLI] = None) -> None:
        self.root = Path(root).resolve()
        self.cli = cli or CRECLI(cwd=self.root)

    def write(self, secret_env_map: Mapping[str, str], path: str | Path = "secrets.yaml") -> Path:
        return write_text(self.root / path, secrets_yaml(secret_env_map), overwrite=True)

    def write_delete(self, secret_names: list[str], path: str | Path = "secrets-to-delete.yaml") -> Path:
        return write_text(self.root / path, secrets_delete_yaml(secret_names), overwrite=True)

    def create(self, path: str | Path = "secrets.yaml", *, target: str = "production-settings", secrets_auth: Optional[str] = None, **kwargs: Any) -> CRECommandResult:
        return self.cli.secrets_create(self.root / path, target=target, secrets_auth=secrets_auth, **kwargs)

    def update(self, path: str | Path = "secrets.yaml", *, target: str = "production-settings", secrets_auth: Optional[str] = None, **kwargs: Any) -> CRECommandResult:
        return self.cli.secrets_update(self.root / path, target=target, secrets_auth=secrets_auth, **kwargs)

    def delete(self, path: str | Path = "secrets-to-delete.yaml", *, target: str = "production-settings", secrets_auth: Optional[str] = None, **kwargs: Any) -> CRECommandResult:
        return self.cli.secrets_delete(self.root / path, target=target, secrets_auth=secrets_auth, **kwargs)

    def list(self, *, target: Optional[str] = None, namespace: Optional[str] = None, secrets_auth: Optional[str] = None) -> CRECommandResult:
        return self.cli.secrets_list(target=target, namespace=namespace, secrets_auth=secrets_auth)


__all__ = ["CRESecrets"]
