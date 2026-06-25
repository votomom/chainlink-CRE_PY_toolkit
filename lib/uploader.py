from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from eth_account import Account
from eth_account.messages import encode_defunct

from .gateway import (
    DEFAULT_GATEWAY_URLS,
    build_gateway_request_json,
    format_curl_command,
    format_curl_command_powershell,
    is_hex_string,
    parse_gateway_urls,
    post_gateway_json_rpc,
    random_message_id_uint32_str,
    sign_eip191_bytes,
)
from .responses import (
    normalize_secrets_set_gateway_response,
    summarize_upload_encrypted_secrets_result,
)

__all__ = [
    "DEFAULT_GATEWAY_URLS",
    "BuiltSecretsPayload",
    "build_gateway_request_json",
    "build_secrets_payload",
    "format_curl_command",
    "format_curl_command_powershell",
    "is_hex_string",
    "normalize_encrypted_secrets_hex",
    "parse_gateway_urls",
    "post_gateway_json_rpc",
    "random_message_id_uint32_str",
    "sign_eip191_bytes",
    "upload_encrypted_secrets_to_don",
]


@dataclass(frozen=True)
class BuiltSecretsPayload:
    payload: Dict[str, Any]
    version: int
    expiration_ms: int
    storage_message_json: str
    signer_address: str


def normalize_encrypted_secrets_hex(value: str, *, base_dir: Optional[Path] = None) -> str:
    raw = (value or "").strip().strip('"').strip("'")
    if not raw:
        raise ValueError("encrypted secrets hex is empty")

    if is_hex_string(raw):
        return raw if raw.startswith("0x") else ("0x" + raw)

    p = Path(raw)
    if not p.is_absolute() and base_dir is not None:
        p = base_dir / p
    if p.exists() and p.is_file():
        file_raw = p.read_text(encoding="utf-8").strip().strip('"').strip("'")
        if not file_raw:
            raise ValueError(f"encrypted secrets file is empty: {p}")
        if not file_raw.startswith("0x"):
            file_raw = "0x" + file_raw
        if not is_hex_string(file_raw):
            raise ValueError(f"encrypted secrets file does not contain hex: {p}")
        return file_raw

    raise ValueError("encrypted secrets must be a hex string (0x...) or a path to a file containing it")


def build_secrets_payload(
    *,
    private_key_hex: str,
    slot_id: int,
    encrypted_secrets_hex: str,
    minutes_until_expiration: int,
    version_override: Optional[int] = None,
    expiration_ms_override: Optional[int] = None,
) -> BuiltSecretsPayload:
    if not encrypted_secrets_hex.startswith("0x"):
        raise ValueError("encrypted_secrets_hex must start with 0x")
    if minutes_until_expiration < 5:
        raise ValueError("minutes_until_expiration must be at least 5")

    acct = Account.from_key(private_key_hex)
    signer_address = acct.address

    signer_address_b64 = base64.b64encode(bytes.fromhex(signer_address[2:])).decode()
    encrypted_secrets_b64 = base64.b64encode(bytes.fromhex(encrypted_secrets_hex[2:])).decode()

    now_sec = int(time.time())
    now_ms = int(time.time() * 1000)
    secrets_version = int(version_override) if version_override is not None else now_sec
    secrets_expiration = (
        int(expiration_ms_override)
        if expiration_ms_override is not None
        else (now_ms + minutes_until_expiration * 60 * 1000)
    )

    storage_message = {
        "address": signer_address_b64,
        "slotid": int(slot_id),
        "payload": encrypted_secrets_b64,
        "version": int(secrets_version),
        "expiration": int(secrets_expiration),
    }
    storage_message_json = json.dumps(storage_message, separators=(",", ":"), ensure_ascii=False)

    storage_sig_hex = sign_eip191_bytes(private_key_hex, storage_message_json.encode("utf-8"))
    storage_signature_b64 = base64.b64encode(bytes.fromhex(storage_sig_hex)).decode()

    payload = {
        "slot_id": int(slot_id),
        "version": int(secrets_version),
        "payload": encrypted_secrets_b64,
        "expiration": int(secrets_expiration),
        "signature": storage_signature_b64,
    }

    return BuiltSecretsPayload(
        payload=payload,
        version=int(secrets_version),
        expiration_ms=int(secrets_expiration),
        storage_message_json=storage_message_json,
        signer_address=signer_address,
    )


def upload_encrypted_secrets_to_don(
    *,
    private_key_hex: str,
    don_id: str,
    gateway_urls: Sequence[str] | str,
    slot_id: int,
    encrypted_secrets_hex_or_path: str,
    minutes_until_expiration: int = 60,
    message_id: Optional[str] = None,
    version_override: Optional[int] = None,
    expiration_ms_override: Optional[int] = None,
    base_dir: Optional[Path] = None,
    debug: bool = False,
) -> Dict[str, Any]:
    gateways = parse_gateway_urls(gateway_urls)
    if not gateways:
        raise ValueError("gateway_urls is empty")

    encrypted_hex = normalize_encrypted_secrets_hex(encrypted_secrets_hex_or_path, base_dir=base_dir)

    built = build_secrets_payload(
        private_key_hex=private_key_hex,
        slot_id=slot_id,
        encrypted_secrets_hex=encrypted_hex,
        minutes_until_expiration=minutes_until_expiration,
        version_override=version_override,
        expiration_ms_override=expiration_ms_override,
    )

    mid = (message_id or "").strip() or random_message_id_uint32_str()

    if debug:
        storage_sig = "0x" + sign_eip191_bytes(private_key_hex, built.storage_message_json.encode("utf-8"))
        storage_rec = Account.recover_message(
            encode_defunct(text=built.storage_message_json),
            signature=storage_sig,
        )
        print(f"[DEBUG] signer_address={built.signer_address}")
        print(f"[DEBUG] storage_signature_recovers={storage_rec}")
        print(f"[DEBUG] storage_message_json={built.storage_message_json}")

    last_err: Optional[Exception] = None

    for gw in gateways:
        try:
            req_json, dbg = build_gateway_request_json(
                private_key_hex=private_key_hex,
                don_id=don_id,
                payload=built.payload,
                message_id=mid,
                method="secrets_set",
                debug=debug,
            )
            if debug:
                print(f"\n[DEBUG] POST {gw} method=secrets_set message_id={mid}")
                for k, v in dbg.items():
                    print(f"[DEBUG] {k}={v}")
                print("[DEBUG] curl_command=")
                print(format_curl_command(gateway_url=gw, request_json=req_json))
                print("[DEBUG] curl_command_powershell=")
                print(format_curl_command_powershell(gateway_url=gw, request_json=req_json))

            result_json = post_gateway_json_rpc(
                gateway_url=gw,
                request_json=req_json,
                timeout_s=30,
                debug=debug,
            )

            normalized = normalize_secrets_set_gateway_response(gateway_url=gw, gateway_json=result_json)
            if not normalized.success:
                if debug:
                    print("[DEBUG] gateway payload.success=false; trying next gateway")
                continue

            return summarize_upload_encrypted_secrets_result(
                gateway_response=normalized,
                secrets_version=built.payload["version"],
            )
        except Exception as exc:
            last_err = exc
            continue

    if last_err is not None:
        raise RuntimeError(f"Failed to send secrets_set to all gateways. Last error: {last_err}") from last_err
    raise RuntimeError("Failed to send secrets_set to all gateways")
