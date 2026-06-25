from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from lib.cre import CRECLI, CREProject, CRESecrets


def _project(args) -> CREProject:
    return CREProject(args.project, root=args.root, dry_run=bool(getattr(args, "dry_run", False)))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Python-first helpers for Chainlink CRE projects.")
    parser.add_argument("--root", default=".", help="Parent directory for generated CRE projects")
    parser.add_argument("--project", default="cre-project", help="CRE project directory/name")
    parser.add_argument("--dry-run", action="store_true", help="show/build commands without calling cre")

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("create", help="create project.yaml, .env, secrets.yaml")

    hello = sub.add_parser("add-hello", help="add a hello-world workflow")
    hello.add_argument("workflow")
    hello.add_argument("--schedule", default="*/30 * * * * *")
    hello.add_argument("--registry", default="private")
    hello.add_argument("--overwrite", action="store_true")

    http = sub.add_parser("add-http-json", help="add cron HTTP JSON workflow")
    http.add_argument("workflow")
    http.add_argument("--schedule", required=True)
    http.add_argument("--url", required=True)
    http.add_argument("--json-path", required=True)
    http.add_argument("--result-type", default="string", choices=("string", "uint256", "int256", "bytes"))
    http.add_argument("--registry", default="private")
    http.add_argument("--overwrite", action="store_true")

    recv = sub.add_parser("receiver", help="write ReceiverTemplate-style Solidity contract")
    recv.add_argument("--contract-name", default="CREReceiver")
    recv.add_argument("--path", default="contracts/CREReceiver.sol")
    recv.add_argument("--overwrite", action="store_true")

    for name in ("build", "simulate", "hash", "deploy", "update", "activate", "pause", "delete"):
        p = sub.add_parser(name, help=f"cre workflow {name}")
        p.add_argument("workflow")
        p.add_argument("--target", default="staging-settings" if name == "simulate" else "production-settings")

    sub.add_parser("list", help="cre workflow list")
    get = sub.add_parser("get", help="cre workflow get")
    get.add_argument("workflow", nargs="?")
    chains = sub.add_parser("supported-chains", help="cre workflow supported-chains")
    chains.set_defaults(cmd="supported-chains")

    sec_write = sub.add_parser("secrets-write", help="write secrets.yaml from KEY=ENV_NAME pairs")
    sec_write.add_argument("pairs", nargs="+")
    sec_write.add_argument("--path", default="secrets.yaml")

    sec_delete_write = sub.add_parser("secrets-write-delete", help="write secrets-to-delete.yaml")
    sec_delete_write.add_argument("names", nargs="+")
    sec_delete_write.add_argument("--path", default="secrets-to-delete.yaml")

    for name in ("secrets-create", "secrets-update", "secrets-delete", "secrets-list"):
        p = sub.add_parser(name, help=f"cre {name.replace('-', ' ')}")
        p.add_argument("--path", default="secrets.yaml" if name != "secrets-delete" else "secrets-to-delete.yaml")
        p.add_argument("--target", default="production-settings")
        p.add_argument("--secrets-auth", default=None)

    args = parser.parse_args(argv)
    project = _project(args)

    if args.cmd == "create":
        print(project.create())
        return 0
    if args.cmd == "add-hello":
        print(project.add_hello_world_workflow(args.workflow, schedule=args.schedule, deployment_registry=args.registry, overwrite=args.overwrite).path)
        return 0
    if args.cmd == "add-http-json":
        print(project.add_http_json_workflow(
            args.workflow,
            schedule=args.schedule,
            url=args.url,
            json_path=args.json_path,
            result_type=args.result_type,
            deployment_registry=args.registry,
            overwrite=args.overwrite,
        ).path)
        return 0
    if args.cmd == "receiver":
        print(project.write_receiver_template(contract_name=args.contract_name, path=args.path, overwrite=args.overwrite))
        return 0

    if args.cmd in ("build", "simulate", "hash", "deploy", "update", "activate", "pause", "delete"):
        result = getattr(project, args.cmd)(args.workflow, target=args.target)
        print(result.stdout, end="")
        print(result.stderr, end="")
        return result.returncode

    cli = CRECLI(cwd=project.root, dry_run=args.dry_run)
    if args.cmd == "list":
        print(cli.workflow_list().stdout, end="")
        return 0
    if args.cmd == "get":
        print(cli.workflow_get(args.workflow).stdout, end="")
        return 0
    if args.cmd == "supported-chains":
        print(cli.workflow_supported_chains().stdout, end="")
        return 0

    secrets = CRESecrets(root=project.root, cli=cli)
    if args.cmd == "secrets-write":
        mapping = dict(pair.split("=", 1) for pair in args.pairs)
        print(secrets.write(mapping, args.path))
        return 0
    if args.cmd == "secrets-write-delete":
        print(secrets.write_delete(args.names, args.path))
        return 0
    if args.cmd == "secrets-create":
        print(secrets.create(args.path, target=args.target, secrets_auth=args.secrets_auth).stdout, end="")
        return 0
    if args.cmd == "secrets-update":
        print(secrets.update(args.path, target=args.target, secrets_auth=args.secrets_auth).stdout, end="")
        return 0
    if args.cmd == "secrets-delete":
        print(secrets.delete(args.path, target=args.target, secrets_auth=args.secrets_auth).stdout, end="")
        return 0
    if args.cmd == "secrets-list":
        print(secrets.list(target=args.target, secrets_auth=args.secrets_auth).stdout, end="")
        return 0

    raise ValueError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
