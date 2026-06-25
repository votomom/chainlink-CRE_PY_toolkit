from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from lib.gateway import DEFAULT_GATEWAY_URLS, parse_gateway_urls
from lib.secrets_list import list_don_hosted_secrets


def _require(value: Optional[str], name: str) -> str:
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _load_env_first(argv: Optional[list[str]]) -> None:
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--env-file", default=os.getenv("ENV_FILE", ".env"))
    pre_args, _ = pre.parse_known_args(argv)
    env_path = Path(pre_args.env_file)
    if env_path.exists():
        load_dotenv(env_path)


def _format_table(rows: list[dict]) -> str:
    if not rows:
        return "(no DON-hosted secrets found)"

    headers = ("slot_id", "version", "expiration_utc")
    formatted = [
        (
            str(r["slot_id"]),
            str(r["version"]),
            datetime.fromtimestamp(r["expiration"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"),
        )
        for r in rows
    ]
    widths = [max(len(h), max((len(row[i]) for row in formatted), default=0)) for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep = "  ".join("-" * w for w in widths)
    body = "\n".join("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in formatted)
    return f"{line}\n{sep}\n{body}"


def main(argv: Optional[list[str]] = None) -> int:
    _load_env_first(argv)

    p = argparse.ArgumentParser(description="List DON-hosted secrets via gateway secrets_list.")
    p.add_argument("--env-file", default=os.getenv("ENV_FILE", ".env"))
    p.add_argument("--private-key", default=os.getenv("PRIVATE_KEY") or os.getenv("DEPLOYER_PRIVATE_KEY"))
    p.add_argument("--don-id", default=os.getenv("CHAINLINK_DON_ID_TEXT", "fun-ethereum-sepolia-1"))
    p.add_argument("--gateway-urls", default=os.getenv("CHAINLINK_GATEWAY_URLS", ",".join(DEFAULT_GATEWAY_URLS)))
    p.add_argument("--message-id", default=os.getenv("CHAINLINK_SECRETS_MESSAGE_ID", ""))
    p.add_argument("--json", action="store_true", help="output raw JSON instead of a table")
    p.add_argument(
        "--debug",
        action="store_true",
        default=os.getenv("CHAINLINK_SECRETS_DEBUG", "").lower() in ("1", "true", "yes", "on"),
    )
    args = p.parse_args(argv)

    result = list_don_hosted_secrets(
        private_key_hex=_require(args.private_key, "private key"),
        don_id=_require(args.don_id, "don id"),
        gateway_urls=parse_gateway_urls(_require(args.gateway_urls, "gateway urls")),
        message_id=(args.message_id.strip() or None) if args.message_id else None,
        debug=bool(args.debug),
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"gateway: {result['gatewayUrl']}  success: {result['success']}")
        print(_format_table(result["rows"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
