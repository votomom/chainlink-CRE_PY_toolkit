from __future__ import annotations

import json
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests
from eth_account import Account
from eth_account.messages import _hash_eip191_message, encode_defunct


MESSAGE_ID_MAX_LEN = 128
MESSAGE_METHOD_MAX_LEN = 64
MESSAGE_DON_ID_MAX_LEN = 64
MESSAGE_RECEIVER_LEN = 42  # "0x" + 40 hex chars

# Trailing slashes match @chainlink/functions-toolkit examples.
DEFAULT_GATEWAY_URLS: Tuple[str, ...] = (
    "https://01.functions-gateway.testnet.chain.link/",
    "https://02.functions-gateway.testnet.chain.link/",
)


def random_message_id_uint32_str() -> str:
    return str(random.randrange(0, 2**32))


def parse_gateway_urls(value: str | Sequence[str]) -> List[str]:
    if isinstance(value, str):
        return [s.strip() for s in value.split(",") if s.strip()]
    return [str(s).strip() for s in value if str(s).strip()]


def is_hex_string(value: str) -> bool:
    raw = (value or "").strip()
    if raw.startswith("0x"):
        raw = raw[2:]
    if not raw:
        return False
    try:
        int(raw, 16)
    except ValueError:
        return False
    return len(raw) % 2 == 0


def sign_eip191_bytes(private_key_hex: str, payload_bytes: bytes) -> str:
    acct = Account.from_key(private_key_hex)
    signed = acct.sign_message(encode_defunct(payload_bytes))
    return signed.signature.hex().removeprefix("0x")


def _pad_bytes(value: str, length: int) -> bytes:
    raw = value.encode("utf-8")
    if len(raw) > length:
        raise ValueError(f"value '{value}' is longer than max length {length}")
    return raw + b"\x00" * (length - len(raw))


def gateway_message_body(
    message_id: str,
    method: str,
    don_id: str,
    receiver: str,
    payload: Optional[Dict[str, Any]],
) -> bytes:
    """
    Reproduces toolkit's createGatewayMessageBody:
    fixed-length aligned fields followed by JSON payload bytes.
    `payload=None` -> empty payload section (used by `secrets_list`).
    """
    payload_json = (
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if payload is not None
        else b""
    )
    return b"".join(
        [
            _pad_bytes(message_id, MESSAGE_ID_MAX_LEN),
            _pad_bytes(method, MESSAGE_METHOD_MAX_LEN),
            _pad_bytes(don_id, MESSAGE_DON_ID_MAX_LEN),
            _pad_bytes(receiver, MESSAGE_RECEIVER_LEN),
            payload_json,
        ]
    )


def build_gateway_request_json(
    *,
    private_key_hex: str,
    don_id: str,
    payload: Optional[Dict[str, Any]],
    message_id: str,
    receiver: str = "",
    method: str = "secrets_set",
    debug: bool = False,
) -> Tuple[str, Dict[str, Any]]:
    body: Dict[str, Any] = {
        "message_id": message_id,
        "method": method,
        "don_id": don_id,
        "receiver": receiver,
    }
    # JSON.stringify in JS drops undefined keys. Match by omitting payload if None.
    if payload is not None:
        body["payload"] = payload

    msg_bytes = gateway_message_body(message_id, method, don_id, receiver, payload)
    sig_hex = sign_eip191_bytes(private_key_hex, msg_bytes)
    gateway_signature = "0x" + sig_hex

    req = {
        "id": message_id,
        "jsonrpc": "2.0",
        "method": method,
        "params": {"body": body, "signature": gateway_signature},
    }
    req_json = json.dumps(req, separators=(",", ":"), ensure_ascii=False)

    dbg: Dict[str, Any] = {}
    if debug:
        recovered = Account.recover_message(
            encode_defunct(msg_bytes), signature=gateway_signature
        )
        dbg = {
            "gateway_body_bytes_len": len(msg_bytes),
            "gateway_eip191_hash": "0x" + _hash_eip191_message(encode_defunct(msg_bytes)).hex(),
            "gateway_signature": gateway_signature,
            "gateway_signature_recovers": recovered,
            "http_request_body_len": len(req_json),
            "http_request_body": req_json,
        }
    return req_json, dbg


def format_curl_command(*, gateway_url: str, request_json: str) -> str:
    return (
        "curl -sS -X POST "
        + json.dumps(gateway_url)
        + " \\\n  -H 'Content-Type: application/json' \\\n"
        + "  --data-binary @- <<'JSON'\n"
        + request_json
        + "\nJSON"
    )


def format_curl_command_powershell(*, gateway_url: str, request_json: str) -> str:
    return (
        "$body = @'\n"
        + request_json
        + "\n'@\n"
        + "$body | curl.exe -sS -X POST "
        + json.dumps(gateway_url)
        + " -H 'Content-Type: application/json' --data-binary @-"
    )


def post_gateway_json_rpc(
    *,
    gateway_url: str,
    request_json: str,
    timeout_s: int = 30,
    debug: bool = False,
) -> Dict[str, Any]:
    response = requests.post(
        gateway_url,
        data=request_json,
        headers={"Content-Type": "application/json"},
        timeout=timeout_s,
    )

    if debug:
        try:
            headers_json = json.dumps(dict(response.headers), indent=2, ensure_ascii=False)
        except Exception:
            headers_json = str(response.headers)
        print(f"\n[DEBUG] HTTP {response.status_code} from {gateway_url}")
        print("[DEBUG] Response headers:")
        print(headers_json)
        print("[DEBUG] Response body:")
        print(response.text)

    if response.status_code >= 400:
        try:
            body: Any = response.json()
        except Exception:
            body = response.text
        raise RuntimeError(f"HTTP {response.status_code} from {gateway_url}: {body}")

    return response.json()


def send_to_gateways(
    *,
    private_key_hex: str,
    don_id: str,
    method: str,
    payload: Optional[Dict[str, Any]],
    gateway_urls: Sequence[str] | str,
    message_id: Optional[str] = None,
    timeout_s: int = 30,
    debug: bool = False,
) -> Tuple[str, Dict[str, Any]]:
    """
    Send a JSON-RPC message to gateways and return `(gateway_url, response_json)`
    from the first gateway that responds with HTTP success.
    """
    gateways = parse_gateway_urls(gateway_urls)
    if not gateways:
        raise ValueError("gateway_urls is empty")
    mid = (message_id or "").strip() or random_message_id_uint32_str()

    last_err: Optional[Exception] = None
    for gw in gateways:
        try:
            req_json, dbg = build_gateway_request_json(
                private_key_hex=private_key_hex,
                don_id=don_id,
                payload=payload,
                message_id=mid,
                method=method,
                debug=debug,
            )
            if debug:
                print(f"\n[DEBUG] POST {gw} method={method} message_id={mid}")
                for k, v in dbg.items():
                    print(f"[DEBUG] {k}={v}")
                print("[DEBUG] curl_command=")
                print(format_curl_command(gateway_url=gw, request_json=req_json))
                print("[DEBUG] curl_command_powershell=")
                print(format_curl_command_powershell(gateway_url=gw, request_json=req_json))

            result_json = post_gateway_json_rpc(
                gateway_url=gw,
                request_json=req_json,
                timeout_s=timeout_s,
                debug=debug,
            )
            return gw, result_json
        except Exception as exc:
            last_err = exc
            continue

    if last_err is not None:
        raise RuntimeError(f"Failed to send {method} to all gateways. Last error: {last_err}") from last_err
    raise RuntimeError(f"Failed to send {method} to all gateways")
