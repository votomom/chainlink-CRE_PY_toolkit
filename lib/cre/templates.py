from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return '""'
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value))


def dump_simple_yaml(data: Mapping[str, Any], indent: int = 0) -> str:
    lines: list[str] = []
    pad = " " * indent
    for key, value in data.items():
        if isinstance(value, Mapping):
            lines.append(f"{pad}{key}:")
            lines.append(dump_simple_yaml(value, indent + 2))
        elif isinstance(value, list):
            lines.append(f"{pad}{key}:")
            for item in value:
                if isinstance(item, Mapping):
                    lines.append(f"{pad}  -")
                    lines.append(dump_simple_yaml(item, indent + 4))
                else:
                    lines.append(f"{pad}  - {_yaml_scalar(item)}")
        else:
            lines.append(f"{pad}{key}: {_yaml_scalar(value)}")
    return "\n".join(lines)


def project_yaml(*, project_name: str, targets: Optional[Mapping[str, Any]] = None) -> str:
    data: Dict[str, Any] = dict(
        targets
        or {
            "staging-settings": {
                "rpcs": [
                    {
                        "chain-name": "ethereum-testnet-sepolia",
                        "url": "https://ethereum-sepolia-rpc.publicnode.com",
                    },
                ],
            },
            "production-settings": {
                "rpcs": [
                    {
                        "chain-name": "ethereum-testnet-sepolia",
                        "url": "${ETHEREUM_SEPOLIA_RPC_URL}",
                    },
                    {
                        "chain-name": "ethereum-mainnet",
                        "url": "${ETHEREUM_MAINNET_RPC_URL}",
                    },
                ],
            },
        },
    )
    return dump_simple_yaml(data) + "\n"


def workflow_yaml(
    *,
    workflow_name: str,
    deployment_registry: str = "private",
    staging_config: str = "./config.staging.json",
    production_config: str = "./config.production.json",
    workflow_path: str = "./main.ts",
    secrets_path: str = "",
) -> str:
    data = {
        "staging-settings": {
            "user-workflow": {
                "workflow-name": f"{workflow_name}-staging",
                "deployment-registry": deployment_registry,
            },
            "workflow-artifacts": {
                "workflow-path": workflow_path,
                "config-path": staging_config,
                "secrets-path": secrets_path,
            },
        },
        "production-settings": {
            "user-workflow": {
                "workflow-name": f"{workflow_name}-production",
                "deployment-registry": deployment_registry,
            },
            "workflow-artifacts": {
                "workflow-path": workflow_path,
                "config-path": production_config,
                "secrets-path": secrets_path,
            },
        },
    }
    return dump_simple_yaml(data) + "\n"


def package_json(*, workflow_name: str, cre_sdk_version: str = "^1.0.0") -> str:
    return json.dumps(
        {
            "name": workflow_name,
            "private": True,
            "type": "module",
            "scripts": {
                "postinstall": "bunx cre-setup",
                "simulate": "cre workflow simulate . --target staging-settings",
            },
            "dependencies": {"@chainlink/cre-sdk": cre_sdk_version},
            "devDependencies": {"@types/bun": "^1.2.21", "typescript": "^5.0.0"},
        },
        indent=2,
    ) + "\n"


def tsconfig_json() -> str:
    return json.dumps(
        {
            "compilerOptions": {
                "target": "ES2022",
                "module": "ESNext",
                "moduleResolution": "Bundler",
                "strict": True,
                "skipLibCheck": True,
                "types": ["bun-types"],
            },
            "include": ["main.ts"],
        },
        indent=2,
    ) + "\n"


def env_template() -> str:
    return (
        "# CRE simulator / onchain registry key. Raw 64-char hex, no 0x prefix.\n"
        "CRE_ETH_PRIVATE_KEY=\n\n"
        "# Optional RPCs used by workflows/config targets.\n"
        "ETHEREUM_SEPOLIA_RPC_URL=\n"
        "ETHEREUM_MAINNET_RPC_URL=\n"
    )


def secrets_yaml(secret_env_map: Mapping[str, str]) -> str:
    return dump_simple_yaml({"secrets": dict(secret_env_map)}) + "\n"


def secrets_delete_yaml(secret_names: Iterable[str]) -> str:
    return dump_simple_yaml({"secretsNames": list(secret_names)}) + "\n"


def hello_world_workflow_ts() -> str:
    return """import { CronCapability, handler, Runner, type Runtime } from "@chainlink/cre-sdk"

type Config = {
  schedule: string
}

const onCronTrigger = (runtime: Runtime<Config>): string => {
  runtime.log("Hello world! Workflow triggered.")
  return "Hello world!"
}

const initWorkflow = (config: Config) => {
  const cron = new CronCapability()
  return [handler(cron.trigger({ schedule: config.schedule }), onCronTrigger)]
}

export async function main() {
  const runner = await Runner.newRunner<Config>()
  await runner.run(initWorkflow)
}
"""


def http_json_workflow_ts(
    *,
    result_type: str = "string",
    write_report: bool = False,
) -> str:
    encode_expr = {
        "uint256": "BigInt(value)",
        "int256": "BigInt(value)",
        "string": "String(value)",
        "bytes": "value",
    }.get(result_type, "String(value)")

    report_line = (
        "\n  // TODO: wire this report into an EVM write capability once receiver config is set.\n"
        "  return runtime.report(encoded)\n"
        if write_report
        else "\n  return encoded\n"
    )

    return f"""import {{ CronCapability, handler, Runner, type Runtime }} from "@chainlink/cre-sdk"

type Config = {{
  schedule: string
  url: string
  jsonPath: string
}}

const pick = (data: unknown, path: string): unknown => {{
  return path.split(".").filter(Boolean).reduce((cur: any, key) => cur?.[key], data as any)
}}

const onCronTrigger = async (runtime: Runtime<Config>): Promise<unknown> => {{
  runtime.log(`Fetching ${{runtime.config.url}}`)

  // The exact HTTP API name can change while CRE is in Early Access.
  // Keep this generated workflow small so it is easy to adjust to the installed SDK.
  const response = await runtime.http.sendRequest({{ url: runtime.config.url, method: "GET" }})
  const value = pick(response.data, runtime.config.jsonPath)

  const encoded = {json.dumps(result_type)} === "bytes"
    ? value
    : {encode_expr}
{report_line}}}

const initWorkflow = (config: Config) => {{
  const cron = new CronCapability()
  return [handler(cron.trigger({{ schedule: config.schedule }}), onCronTrigger)]
}}

export async function main() {{
  const runner = await Runner.newRunner<Config>()
  await runner.run(initWorkflow)
}}
"""


def receiver_template_sol(contract_name: str = "CREReceiver") -> str:
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

interface IReceiver {{
    function onReport(bytes calldata metadata, bytes calldata payload) external;
}}

contract {contract_name} is IReceiver {{
    address public owner;
    bytes public lastMetadata;
    bytes public lastPayload;

    event ReportReceived(bytes metadata, bytes payload);

    modifier onlyOwner() {{
        require(msg.sender == owner, "not owner");
        _;
    }}

    constructor() {{
        owner = msg.sender;
    }}

    function onReport(bytes calldata metadata, bytes calldata payload) external override {{
        lastMetadata = metadata;
        lastPayload = payload;
        emit ReportReceived(metadata, payload);
    }}
}}
"""


def write_text(path: str | Path, content: str, *, overwrite: bool = False) -> Path:
    p = Path(path)
    if p.exists() and not overwrite:
        raise FileExistsError(f"{p} already exists")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


__all__ = [
    "dump_simple_yaml",
    "env_template",
    "hello_world_workflow_ts",
    "http_json_workflow_ts",
    "package_json",
    "project_yaml",
    "receiver_template_sol",
    "secrets_delete_yaml",
    "secrets_yaml",
    "tsconfig_json",
    "workflow_yaml",
    "write_text",
]
