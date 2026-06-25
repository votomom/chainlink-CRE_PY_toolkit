from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SecretsEntry:
    slot_id: int
    version: int
    expiration: int


@dataclass(frozen=True)
class NodeResponse:
    success: bool
    error_message: Optional[str] = None
    rows: List[SecretsEntry] = field(default_factory=list)


@dataclass(frozen=True)
class SecretsSetGatewayResponse:
    gateway_url: str
    success: bool
    node_responses: List[NodeResponse]


@dataclass(frozen=True)
class SecretsListGatewayResponse:
    gateway_url: str
    success: bool
    node_responses: List[NodeResponse]


def _get(obj: Any, path: List[str]) -> Any:
    cur: Any = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            raise ValueError(f"missing field: {'.'.join(path)}")
        cur = cur[key]
    return cur


def _raise_if_jsonrpc_error(gateway_json: Dict[str, Any]) -> None:
    if "error" in gateway_json:
        err = gateway_json.get("error") or {}
        raise ValueError(
            f"gateway_error code={err.get('code')} message={err.get('message')} raw={gateway_json}"
        )


def _parse_node_response(entry: Dict[str, Any]) -> NodeResponse:
    try:
        node_payload = _get(entry, ["body", "payload"])
    except Exception:
        node_payload = {}

    success = bool(node_payload.get("success", False))
    err = node_payload.get("error_message")
    err_str = err if isinstance(err, str) else None

    rows_raw = node_payload.get("rows") or []
    rows: List[SecretsEntry] = []
    if isinstance(rows_raw, list):
        for r in rows_raw:
            if not isinstance(r, dict):
                continue
            try:
                rows.append(
                    SecretsEntry(
                        slot_id=int(r["slot_id"]),
                        version=int(r["version"]),
                        expiration=int(r["expiration"]),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue

    return NodeResponse(success=success, error_message=err_str, rows=rows)


def normalize_secrets_set_gateway_response(
    *, gateway_url: str, gateway_json: Dict[str, Any]
) -> SecretsSetGatewayResponse:
    _raise_if_jsonrpc_error(gateway_json)

    payload = _get(gateway_json, ["result", "body", "payload"])
    if not isinstance(payload, dict):
        raise ValueError(f"unexpected payload type: {type(payload)}")

    raw_node_responses = payload.get("node_responses") or []
    if not isinstance(raw_node_responses, list) or not raw_node_responses:
        raise ValueError("payload.node_responses is empty or not a list")

    return SecretsSetGatewayResponse(
        gateway_url=gateway_url,
        success=bool(payload.get("success", False)),
        node_responses=[_parse_node_response(e) for e in raw_node_responses],
    )


def normalize_secrets_list_gateway_response(
    *, gateway_url: str, gateway_json: Dict[str, Any]
) -> SecretsListGatewayResponse:
    _raise_if_jsonrpc_error(gateway_json)

    payload = _get(gateway_json, ["result", "body", "payload"])
    if not isinstance(payload, dict):
        raise ValueError(f"unexpected payload type: {type(payload)}")

    raw_node_responses = payload.get("node_responses") or []
    if not isinstance(raw_node_responses, list) or not raw_node_responses:
        raise ValueError("payload.node_responses is empty or not a list")

    return SecretsListGatewayResponse(
        gateway_url=gateway_url,
        success=bool(payload.get("success", False)),
        node_responses=[_parse_node_response(e) for e in raw_node_responses],
    )


def summarize_upload_encrypted_secrets_result(
    *,
    gateway_response: SecretsSetGatewayResponse,
    secrets_version: int,
) -> Dict[str, Any]:
    """
    Mirrors toolkit semantics:
    - all nodes failed -> raise
    - some nodes failed -> success=false (version still returned)
    - all nodes succeeded -> success=true
    """
    total = len(gateway_response.node_responses)
    failed = sum(1 for nr in gateway_response.node_responses if not nr.success)

    if failed == total:
        raise RuntimeError("All nodes failed to store the encrypted secrets")

    return {
        "version": int(secrets_version),
        "success": failed == 0,
        "gatewayUrl": gateway_response.gateway_url,
        "nodeResponses": [
            {"success": nr.success, "error_message": nr.error_message}
            for nr in gateway_response.node_responses
        ],
    }


def merge_listed_secrets(response: SecretsListGatewayResponse) -> List[SecretsEntry]:
    """
    Returns the union of slot/version entries reported by responding nodes,
    deduplicated by (slot_id, version). Useful when nodes are out of sync.
    """
    seen: Dict[tuple, SecretsEntry] = {}
    for nr in response.node_responses:
        if not nr.success:
            continue
        for row in nr.rows:
            key = (row.slot_id, row.version)
            seen.setdefault(key, row)
    return sorted(seen.values(), key=lambda r: (r.slot_id, r.version))
