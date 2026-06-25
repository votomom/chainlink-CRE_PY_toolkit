from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from .project import CREProject, CREWorkflow
from .templates import write_text


CONCEPT_MAPPING = {
    "FunctionsClient": "ReceiverTemplate / IReceiver",
    "_sendRequest": "CRE trigger + workflow callback",
    "fulfillRequest": "_onReport(metadata, payload)",
    "Functions.makeHttpRequest": "runtime.http.sendRequest",
    "DON-hosted secrets": "CRE Vault secrets (`cre secrets create/update/delete`)",
    "simulateScript": "cre workflow simulate",
    "uploadEncryptedSecretsToDON": "cre secrets create/update",
    "SubscriptionManager": "cre workflow deploy/activate/pause/delete + registry settings",
}


@dataclass(frozen=True)
class FunctionsToCREMigration:
    project: CREProject
    workflow: CREWorkflow
    notes_path: Path


def migration_notes(*, source_summary: str = "", receiver_contract: str = "CREReceiver") -> str:
    mapping = "\n".join(f"- `{old}` -> `{new}`" for old, new in CONCEPT_MAPPING.items())
    return f"""# Chainlink Functions -> CRE Migration Notes

{source_summary}

## Concept mapping

{mapping}

## Manual steps

1. Move request trigger logic out of the old `FunctionsClient` contract.
2. Pick a CRE trigger: cron, HTTP, or EVM log.
3. Move inline JavaScript into the generated `main.ts` workflow callback.
4. Move secrets to CRE Vault using `cre secrets create`.
5. Replace `fulfillRequest(bytes32,bytes,bytes)` with `{receiver_contract}.onReport(...)`.
6. Run `cre workflow simulate` before deploying.
7. Deploy, activate, and only then decommission the old CLF subscription.
"""


def scaffold_from_functions_request(
    *,
    project_name: str,
    workflow_name: str,
    root: str | Path = ".",
    schedule: str = "*/30 * * * * *",
    source: Optional[str] = None,
    args: Optional[list[str]] = None,
    secrets: Optional[Mapping[str, str]] = None,
    deployment_registry: str = "private",
    overwrite: bool = False,
) -> FunctionsToCREMigration:
    project = CREProject(project_name, root=root)
    project.create(overwrite=overwrite)
    workflow = project.add_hello_world_workflow(
        workflow_name,
        schedule=schedule,
        deployment_registry=deployment_registry,
        overwrite=overwrite,
    )

    if source:
        main = workflow.path / "main.ts"
        existing = main.read_text(encoding="utf-8")
        migrated_comment = (
            "\n/*\n"
            "Original Chainlink Functions source. Move this logic into the CRE callback and replace\n"
            "`Functions.makeHttpRequest` / `Functions.encode*` calls with CRE SDK capabilities.\n\n"
            f"{source}\n"
            "*/\n"
        )
        main.write_text(existing + migrated_comment, encoding="utf-8")

    if secrets:
        project.write_secrets_file(secrets, overwrite=True)

    notes = project.root / "MIGRATION.md"
    write_text(
        notes,
        migration_notes(
            source_summary=f"- Original args: `{args or []}`\n- Original secrets: `{list((secrets or {}).keys())}`",
        ),
        overwrite=overwrite,
    )
    project.write_receiver_template(overwrite=overwrite)
    return FunctionsToCREMigration(project=project, workflow=workflow, notes_path=notes)


__all__ = [
    "CONCEPT_MAPPING",
    "FunctionsToCREMigration",
    "migration_notes",
    "scaffold_from_functions_request",
]
