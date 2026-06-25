from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any, Iterable, Mapping, Optional, Union


class Location(IntEnum):
    Inline = 0
    Remote = 1
    DONHosted = 2
    INLINE = 0
    REMOTE = 1
    DON_HOSTED = 2


class CodeLanguage(IntEnum):
    JavaScript = 0
    JAVASCRIPT = 0


class ReturnType(str, Enum):
    uint = "uint256"
    uint256 = "uint256"
    int = "int256"
    int256 = "int256"
    string = "string"
    bytes = "bytes"


# Names match the toolkit `ReturnType` enum.
RETURN_TYPES = ("uint256", "int256", "string", "bytes")


@dataclass(frozen=True)
class FunctionsRequestParams:
    source: str
    code_location: Location = Location.INLINE
    code_language: CodeLanguage = CodeLanguage.JAVASCRIPT
    secrets_location: Optional[Location] = None
    encrypted_secrets_reference: Optional[str] = None  # 0x-hex
    args: Optional[Iterable[str]] = None
    bytes_args: Optional[Iterable[str]] = None  # iterable of 0x-hex


def _strip_hex(value: str) -> bytes:
    s = value.strip()
    if not s.startswith("0x"):
        raise ValueError(f"expected 0x-prefixed hex, got: {value!r}")
    return bytes.fromhex(s[2:])


def _coerce_params(params: FunctionsRequestParams | Mapping[str, Any]) -> FunctionsRequestParams:
    if isinstance(params, FunctionsRequestParams):
        return params
    return FunctionsRequestParams(
        source=params.get("source"),
        code_location=Location(params.get("codeLocation", params.get("code_location", Location.INLINE))),
        code_language=CodeLanguage(params.get("codeLanguage", params.get("code_language", CodeLanguage.JAVASCRIPT))),
        secrets_location=(
            Location(params["secretsLocation"])
            if "secretsLocation" in params
            else (Location(params["secrets_location"]) if "secrets_location" in params else None)
        ),
        encrypted_secrets_reference=params.get("encryptedSecretsReference") or params.get("encrypted_secrets_reference"),
        args=params.get("args"),
        bytes_args=params.get("bytesArgs") or params.get("bytes_args"),
    )


def build_request_cbor(params: FunctionsRequestParams | Mapping[str, Any]) -> str:
    """
    CBOR-encode a Functions request, mirroring `buildRequestCBOR` from the JS toolkit.
    Returns a 0x-prefixed hex string suitable for `FunctionsRouter.sendRequest(data, ...)`.
    """
    try:
        import cbor2
    except ModuleNotFoundError as exc:
        raise RuntimeError("build_request_cbor requires `cbor2` (pip install cbor2)") from exc

    params = _coerce_params(params)

    if params.code_location != Location.INLINE:
        raise ValueError("only inline codeLocation is supported by Chainlink Functions")
    if params.code_language != CodeLanguage.JAVASCRIPT:
        raise ValueError("only JavaScript codeLanguage is supported")
    if not isinstance(params.source, str) or not params.source:
        raise ValueError("source must be a non-empty string")

    request: dict = {
        "codeLocation": int(params.code_location),
        "codeLanguage": int(params.code_language),
        "source": params.source,
    }

    if params.encrypted_secrets_reference:
        if params.secrets_location not in (Location.DON_HOSTED, Location.REMOTE):
            raise ValueError("secrets_location must be DON_HOSTED or REMOTE when secrets are set")
        request["secretsLocation"] = int(params.secrets_location)
        request["secrets"] = _strip_hex(params.encrypted_secrets_reference)

    if params.args is not None:
        args = list(params.args)
        if not all(isinstance(a, str) for a in args):
            raise ValueError("args must be list[str]")
        if args:
            request["args"] = args

    if params.bytes_args is not None:
        bytes_args = [_strip_hex(a) for a in params.bytes_args]
        if bytes_args:
            request["bytesArgs"] = bytes_args

    encoded = cbor2.dumps(request, canonical=True)
    return "0x" + encoded.hex()


def build_don_hosted_secrets_reference(
    *,
    slot_id: Optional[int] = None,
    version: int,
    slotId: Optional[int] = None,
) -> str:
    """
    Build the `encryptedSecretsReference` for DON-hosted secrets.

    Matches `SecretsManager.buildDONHostedEncryptedSecretsReference` in the
    JS toolkit: CBOR-encodes `{slotId, version}` and returns 0x-hex.
    """
    try:
        import cbor2
    except ModuleNotFoundError as exc:
        raise RuntimeError("build_don_hosted_secrets_reference requires `cbor2`") from exc

    slot = slot_id if slot_id is not None else slotId
    if not isinstance(slot, int) or slot < 0:
        raise ValueError("slot_id must be a non-negative integer")
    if not isinstance(version, int) or version < 0:
        raise ValueError("version must be a non-negative integer")

    return "0x" + cbor2.dumps({"slotId": slot, "version": version}, canonical=True).hex()


def decode_response(response_hex: str, return_type: str | ReturnType) -> Union[int, str, bytes]:
    """
    Decode the raw response bytes returned by a Functions DON.

    Mirrors the toolkit's `decodeResult`: response bytes are produced by the
    Functions JS source (e.g. `Functions.encodeUint256`) and are NOT ABI-
    length-prefixed. Decoding takes the trailing 32 bytes for numeric types.
    """
    rt = return_type.value if isinstance(return_type, ReturnType) else return_type.lower().strip()
    if rt not in RETURN_TYPES:
        raise ValueError(f"return_type must be one of {RETURN_TYPES}, got {return_type!r}")

    raw = response_hex.strip()
    if not raw.startswith("0x"):
        raise ValueError("response_hex must be 0x-prefixed")

    body = raw[2:]
    if rt in ("uint256", "int256"):
        if len(body) > 64:
            raise ValueError(f"too many bytes for {rt}: {len(body)//2}")
        if not body:
            return 0
        last_word = int(body[-64:], 16)
        if rt == "uint256":
            return last_word
        # two's complement to signed 256-bit
        if last_word >= 1 << 255:
            return last_word - (1 << 256)
        return last_word

    if rt == "string":
        return bytes.fromhex(body).decode("utf-8") if body else ""

    return bytes.fromhex(body)


buildRequestCBOR = build_request_cbor
buildDONHostedEncryptedSecretsReference = build_don_hosted_secrets_reference
decodeResult = decode_response
