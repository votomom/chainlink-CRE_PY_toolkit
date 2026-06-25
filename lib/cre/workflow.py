from __future__ import annotations

from pathlib import Path
from typing import Optional

from .cli import CRECLI, CRECommandResult


class CREWorkflowClient:
    def __init__(self, *, root: str | Path = ".", cli: Optional[CRECLI] = None) -> None:
        self.root = Path(root).resolve()
        self.cli = cli or CRECLI(cwd=self.root)

    def build(self, workflow: str | Path, *, target: Optional[str] = None, output: Optional[str | Path] = None) -> CRECommandResult:
        return self.cli.workflow_build(workflow, target=target, output=output)

    def simulate(self, workflow: str | Path, *, target: str = "staging-settings") -> CRECommandResult:
        return self.cli.workflow_simulate(workflow, target=target)

    def hash(self, workflow: str | Path, *, target: Optional[str] = None) -> CRECommandResult:
        return self.cli.workflow_hash(workflow, target=target)

    def deploy(self, workflow: str | Path, *, target: str = "production-settings", unsigned: bool = False) -> CRECommandResult:
        return self.cli.workflow_deploy(workflow, target=target, unsigned=unsigned)

    def update(self, workflow: str | Path, *, target: str = "production-settings", unsigned: bool = False) -> CRECommandResult:
        return self.deploy(workflow, target=target, unsigned=unsigned)

    def activate(self, workflow: str | Path, *, target: str = "production-settings") -> CRECommandResult:
        return self.cli.workflow_activate(workflow, target=target)

    def pause(self, workflow: str | Path, *, target: str = "production-settings") -> CRECommandResult:
        return self.cli.workflow_pause(workflow, target=target)

    def delete(self, workflow: str | Path, *, target: str = "production-settings") -> CRECommandResult:
        return self.cli.workflow_delete(workflow, target=target)

    def list(self, *, target: Optional[str] = None) -> CRECommandResult:
        return self.cli.workflow_list(target=target)

    def get(self, workflow: Optional[str | Path] = None, *, target: Optional[str] = None) -> CRECommandResult:
        return self.cli.workflow_get(workflow, target=target)

    def supported_chains(self) -> CRECommandResult:
        return self.cli.workflow_supported_chains()

    def custom_build(self, workflow: str | Path, *, target: Optional[str] = None, extra_args: tuple[str, ...] = ()) -> CRECommandResult:
        return self.cli.workflow_custom_build(workflow, target=target, extra_args=extra_args)


__all__ = ["CREWorkflowClient"]
