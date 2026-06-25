from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class CRECommandResult:
    args: List[str]
    returncode: int
    stdout: str
    stderr: str

    def json(self) -> Any:
        text = self.stdout.strip()
        if not text:
            return None
        return json.loads(text)


class CRECLI:
    def __init__(
        self,
        *,
        cre_binary: str = "cre",
        cwd: Optional[str | Path] = None,
        env: Optional[Dict[str, str]] = None,
        dry_run: bool = False,
    ) -> None:
        self.cre_binary = cre_binary
        self.cwd = Path(cwd).resolve() if cwd is not None else None
        self.env = env
        self.dry_run = dry_run

    def ensure_installed(self) -> None:
        if shutil.which(self.cre_binary) is None:
            raise RuntimeError(f"`{self.cre_binary}` CLI is not installed or not on PATH")

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Optional[str | Path] = None,
        check: bool = True,
        capture_output: bool = True,
        input_text: Optional[str] = None,
    ) -> CRECommandResult:
        cmd = [self.cre_binary, *map(str, args)]
        run_cwd = Path(cwd).resolve() if cwd is not None else self.cwd
        if self.dry_run:
            return CRECommandResult(args=cmd, returncode=0, stdout="", stderr="")

        self.ensure_installed()
        proc = subprocess.run(
            cmd,
            cwd=str(run_cwd) if run_cwd is not None else None,
            env=self.env,
            input=input_text,
            text=True,
            capture_output=capture_output,
        )
        result = CRECommandResult(cmd, proc.returncode, proc.stdout or "", proc.stderr or "")
        if check and proc.returncode != 0:
            raise RuntimeError(
                f"CRE command failed ({proc.returncode}): {' '.join(cmd)}\n{result.stderr or result.stdout}"
            )
        return result

    def login(self) -> CRECommandResult:
        return self.run(["login"], capture_output=False)

    def whoami(self, *, output_json: bool = False) -> CRECommandResult:
        args = ["whoami"]
        if output_json:
            args += ["--output", "json"]
        return self.run(args)

    def account_access(self) -> CRECommandResult:
        return self.run(["account", "access"], capture_output=False)

    def account_link_key(self, *extra_args: str) -> CRECommandResult:
        return self.run(["account", "link-key", *extra_args], capture_output=False)

    def init(self, *extra_args: str, non_interactive: bool = False) -> CRECommandResult:
        args = ["init"]
        if non_interactive:
            args.append("--non-interactive")
        args += list(extra_args)
        return self.run(args, capture_output=not non_interactive)

    def generate_bindings(self, *extra_args: str) -> CRECommandResult:
        return self.run(["generate-bindings", *extra_args])

    def registry_list(self, *, output_json: bool = True) -> CRECommandResult:
        args = ["registry", "list"]
        if output_json:
            args += ["--output", "json"]
        return self.run(args)

    def workflow(
        self,
        command: str,
        workflow: Optional[str | Path] = None,
        *,
        target: Optional[str] = None,
        output_json: bool = False,
        extra_args: Iterable[str] = (),
    ) -> CRECommandResult:
        args = ["workflow", command]
        if workflow is not None:
            args.append(str(workflow))
        if target:
            args += ["--target", target]
        if output_json:
            args += ["--output", "json"]
        args += list(extra_args)
        return self.run(args)

    def workflow_build(self, workflow: str | Path, *, target: Optional[str] = None, output: Optional[str | Path] = None) -> CRECommandResult:
        extra = ["--output", str(output)] if output else []
        return self.workflow("build", workflow, target=target, extra_args=extra)

    def workflow_simulate(self, workflow: str | Path, *, target: str = "staging-settings", extra_args: Iterable[str] = ()) -> CRECommandResult:
        return self.workflow("simulate", workflow, target=target, extra_args=extra_args)

    def workflow_hash(self, workflow: str | Path, *, target: Optional[str] = None, output_json: bool = True) -> CRECommandResult:
        return self.workflow("hash", workflow, target=target, output_json=output_json)

    def workflow_deploy(self, workflow: str | Path, *, target: str = "production-settings", unsigned: bool = False) -> CRECommandResult:
        extra = ["--unsigned"] if unsigned else []
        return self.workflow("deploy", workflow, target=target, extra_args=extra)

    def workflow_activate(self, workflow: str | Path, *, target: str = "production-settings") -> CRECommandResult:
        return self.workflow("activate", workflow, target=target)

    def workflow_pause(self, workflow: str | Path, *, target: str = "production-settings") -> CRECommandResult:
        return self.workflow("pause", workflow, target=target)

    def workflow_delete(self, workflow: str | Path, *, target: str = "production-settings") -> CRECommandResult:
        return self.workflow("delete", workflow, target=target)

    def workflow_list(self, *, target: Optional[str] = None, output_json: bool = True) -> CRECommandResult:
        return self.workflow("list", None, target=target, output_json=output_json)

    def workflow_get(self, workflow: Optional[str | Path] = None, *, target: Optional[str] = None, output_json: bool = True) -> CRECommandResult:
        return self.workflow("get", workflow, target=target, output_json=output_json)

    def workflow_supported_chains(self, *, output_json: bool = True) -> CRECommandResult:
        return self.workflow("supported-chains", None, output_json=output_json)

    def workflow_custom_build(self, workflow: str | Path, *, target: Optional[str] = None, extra_args: Iterable[str] = ()) -> CRECommandResult:
        return self.workflow("custom-build", workflow, target=target, extra_args=extra_args)

    def secrets(
        self,
        command: str,
        secrets_file: Optional[str | Path] = None,
        *,
        target: Optional[str] = None,
        namespace: Optional[str] = None,
        secrets_auth: Optional[str] = None,
        unsigned: bool = False,
        timeout: Optional[str] = None,
        output_json: bool = False,
    ) -> CRECommandResult:
        args = ["secrets", command]
        if secrets_file is not None:
            args.append(str(secrets_file))
        if target:
            args += ["--target", target]
        if namespace:
            args += ["--namespace", namespace]
        if secrets_auth:
            args += ["--secrets-auth", secrets_auth]
        if unsigned:
            args.append("--unsigned")
        if timeout:
            args += ["--timeout", timeout]
        if output_json:
            args += ["--output", "json"]
        return self.run(args)

    def secrets_create(self, secrets_file: str | Path, **kwargs: Any) -> CRECommandResult:
        return self.secrets("create", secrets_file, **kwargs)

    def secrets_update(self, secrets_file: str | Path, **kwargs: Any) -> CRECommandResult:
        return self.secrets("update", secrets_file, **kwargs)

    def secrets_delete(self, secrets_file: str | Path, **kwargs: Any) -> CRECommandResult:
        return self.secrets("delete", secrets_file, **kwargs)

    def secrets_list(self, **kwargs: Any) -> CRECommandResult:
        kwargs.setdefault("output_json", True)
        return self.secrets("list", None, **kwargs)


__all__ = ["CRECLI", "CRECommandResult"]
