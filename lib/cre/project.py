from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .cli import CRECLI, CRECommandResult
from .templates import (
    env_template,
    hello_world_workflow_ts,
    http_json_workflow_ts,
    package_json,
    project_yaml,
    receiver_template_sol,
    secrets_delete_yaml,
    secrets_yaml,
    tsconfig_json,
    workflow_yaml,
    write_text,
)


@dataclass(frozen=True)
class CREWorkflow:
    name: str
    path: Path


class CREProject:
    def __init__(
        self,
        name: str,
        *,
        root: str | Path = ".",
        cre_binary: str = "cre",
        dry_run: bool = False,
    ) -> None:
        self.name = name
        self.root = Path(root).resolve() / name
        self.cli = CRECLI(cre_binary=cre_binary, cwd=self.root, dry_run=dry_run)

    def create(
        self,
        *,
        overwrite: bool = False,
        targets: Optional[Mapping[str, Any]] = None,
    ) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        write_text(self.root / "project.yaml", project_yaml(project_name=self.name, targets=targets), overwrite=overwrite)
        write_text(self.root / "secrets.yaml", secrets_yaml({}), overwrite=overwrite)
        write_text(self.root / ".env", env_template(), overwrite=overwrite)
        write_text(self.root / ".gitignore", ".env\nnode_modules/\ndist/\n*.wasm\n", overwrite=overwrite)
        return self.root

    def init_with_cre_cli(self, *extra_args: str, non_interactive: bool = False) -> CRECommandResult:
        self.root.parent.mkdir(parents=True, exist_ok=True)
        return CRECLI(cwd=self.root.parent).init(*extra_args, non_interactive=non_interactive)

    def workflow_path(self, workflow_name: str) -> Path:
        return self.root / workflow_name

    def add_hello_world_workflow(
        self,
        name: str,
        *,
        schedule: str = "*/30 * * * * *",
        deployment_registry: str = "private",
        overwrite: bool = False,
    ) -> CREWorkflow:
        path = self.workflow_path(name)
        path.mkdir(parents=True, exist_ok=True)
        write_text(path / "main.ts", hello_world_workflow_ts(), overwrite=overwrite)
        write_text(path / "package.json", package_json(workflow_name=name), overwrite=overwrite)
        write_text(path / "tsconfig.json", tsconfig_json(), overwrite=overwrite)
        write_text(path / "workflow.yaml", workflow_yaml(workflow_name=name, deployment_registry=deployment_registry), overwrite=overwrite)
        write_text(path / "config.staging.json", json.dumps({"schedule": schedule}, indent=2) + "\n", overwrite=overwrite)
        write_text(path / "config.production.json", json.dumps({"schedule": schedule}, indent=2) + "\n", overwrite=overwrite)
        write_text(path / "README.md", f"# {name}\n\nGenerated CRE TypeScript workflow.\n", overwrite=overwrite)
        return CREWorkflow(name=name, path=path)

    def add_http_json_workflow(
        self,
        name: str,
        *,
        schedule: str,
        url: str,
        json_path: str,
        result_type: str = "string",
        deployment_registry: str = "private",
        write_report: bool = False,
        overwrite: bool = False,
    ) -> CREWorkflow:
        path = self.workflow_path(name)
        path.mkdir(parents=True, exist_ok=True)
        config = {"schedule": schedule, "url": url, "jsonPath": json_path}
        write_text(path / "main.ts", http_json_workflow_ts(result_type=result_type, write_report=write_report), overwrite=overwrite)
        write_text(path / "package.json", package_json(workflow_name=name), overwrite=overwrite)
        write_text(path / "tsconfig.json", tsconfig_json(), overwrite=overwrite)
        write_text(path / "workflow.yaml", workflow_yaml(workflow_name=name, deployment_registry=deployment_registry), overwrite=overwrite)
        write_text(path / "config.staging.json", json.dumps(config, indent=2) + "\n", overwrite=overwrite)
        write_text(path / "config.production.json", json.dumps(config, indent=2) + "\n", overwrite=overwrite)
        write_text(path / "README.md", f"# {name}\n\nGenerated HTTP JSON CRE workflow.\n", overwrite=overwrite)
        return CREWorkflow(name=name, path=path)

    def write_receiver_template(
        self,
        *,
        contract_name: str = "CREReceiver",
        path: str | Path = "contracts/CREReceiver.sol",
        overwrite: bool = False,
    ) -> Path:
        return write_text(self.root / path, receiver_template_sol(contract_name), overwrite=overwrite)

    def write_secrets_file(
        self,
        secret_env_map: Mapping[str, str],
        *,
        path: str | Path = "secrets.yaml",
        overwrite: bool = True,
    ) -> Path:
        return write_text(self.root / path, secrets_yaml(secret_env_map), overwrite=overwrite)

    def write_secrets_delete_file(
        self,
        secret_names: list[str],
        *,
        path: str | Path = "secrets-to-delete.yaml",
        overwrite: bool = True,
    ) -> Path:
        return write_text(self.root / path, secrets_delete_yaml(secret_names), overwrite=overwrite)

    def install_workflow_deps(self, workflow: str | CREWorkflow) -> CRECommandResult:
        wf = workflow.path if isinstance(workflow, CREWorkflow) else self.workflow_path(workflow)
        if self.cli.dry_run:
            return CRECommandResult(args=["bun", "install"], returncode=0, stdout="", stderr="")
        proc = subprocess.run(["bun", "install"], cwd=str(wf), text=True, capture_output=True)
        result = CRECommandResult(["bun", "install"], proc.returncode, proc.stdout or "", proc.stderr or "")
        if proc.returncode != 0:
            raise RuntimeError(f"bun install failed:\n{result.stderr or result.stdout}")
        return result

    def build(self, workflow: str | CREWorkflow, *, target: Optional[str] = None, output: Optional[str | Path] = None) -> CRECommandResult:
        wf = workflow.path if isinstance(workflow, CREWorkflow) else self.workflow_path(workflow)
        return self.cli.workflow_build(wf, target=target, output=output)

    def simulate(self, workflow: str | CREWorkflow, *, target: str = "staging-settings") -> CRECommandResult:
        wf = workflow.path if isinstance(workflow, CREWorkflow) else self.workflow_path(workflow)
        return self.cli.workflow_simulate(wf, target=target)

    def hash(self, workflow: str | CREWorkflow, *, target: Optional[str] = None) -> CRECommandResult:
        wf = workflow.path if isinstance(workflow, CREWorkflow) else self.workflow_path(workflow)
        return self.cli.workflow_hash(wf, target=target)

    def deploy(self, workflow: str | CREWorkflow, *, target: str = "production-settings", unsigned: bool = False) -> CRECommandResult:
        wf = workflow.path if isinstance(workflow, CREWorkflow) else self.workflow_path(workflow)
        return self.cli.workflow_deploy(wf, target=target, unsigned=unsigned)

    def update(self, workflow: str | CREWorkflow, *, target: str = "production-settings", unsigned: bool = False) -> CRECommandResult:
        return self.deploy(workflow, target=target, unsigned=unsigned)

    def activate(self, workflow: str | CREWorkflow, *, target: str = "production-settings") -> CRECommandResult:
        wf = workflow.path if isinstance(workflow, CREWorkflow) else self.workflow_path(workflow)
        return self.cli.workflow_activate(wf, target=target)

    def pause(self, workflow: str | CREWorkflow, *, target: str = "production-settings") -> CRECommandResult:
        wf = workflow.path if isinstance(workflow, CREWorkflow) else self.workflow_path(workflow)
        return self.cli.workflow_pause(wf, target=target)

    def delete(self, workflow: str | CREWorkflow, *, target: str = "production-settings") -> CRECommandResult:
        wf = workflow.path if isinstance(workflow, CREWorkflow) else self.workflow_path(workflow)
        return self.cli.workflow_delete(wf, target=target)

    def list_workflows(self, *, target: Optional[str] = None) -> CRECommandResult:
        return self.cli.workflow_list(target=target)

    def get_workflow(self, workflow: Optional[str | CREWorkflow] = None, *, target: Optional[str] = None) -> CRECommandResult:
        wf = workflow.path if isinstance(workflow, CREWorkflow) else (self.workflow_path(workflow) if workflow else None)
        return self.cli.workflow_get(wf, target=target)

    def secrets_create(self, secrets_file: str | Path = "secrets.yaml", **kwargs: Any) -> CRECommandResult:
        return self.cli.secrets_create(self.root / secrets_file, **kwargs)

    def secrets_update(self, secrets_file: str | Path = "secrets.yaml", **kwargs: Any) -> CRECommandResult:
        return self.cli.secrets_update(self.root / secrets_file, **kwargs)

    def secrets_delete(self, secrets_file: str | Path = "secrets-to-delete.yaml", **kwargs: Any) -> CRECommandResult:
        return self.cli.secrets_delete(self.root / secrets_file, **kwargs)

    def secrets_list(self, **kwargs: Any) -> CRECommandResult:
        return self.cli.secrets_list(**kwargs)


__all__ = ["CREProject", "CREWorkflow"]
