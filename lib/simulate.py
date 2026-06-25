from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


DEFAULT_MAX_ON_CHAIN_RESPONSE_BYTES = 256
DEFAULT_MAX_EXECUTION_DURATION_MS = 10_000
DEFAULT_MAX_MEMORY_USAGE_MB = 128
DEFAULT_MAX_HTTP_REQUESTS = 5
DEFAULT_MAX_HTTP_REQUEST_DURATION_MS = 9_000
DEFAULT_MAX_HTTP_REQUEST_URL_LENGTH = 2048
DEFAULT_MAX_HTTP_REQUEST_BYTES = 1024 * 30
DEFAULT_MAX_HTTP_RESPONSE_BYTES = 2_097_152


@dataclass(frozen=True)
class SimulationResult:
    capturedTerminalOutput: str
    responseBytesHexstring: Optional[str] = None
    errorString: Optional[str] = None


def _b64_json(value: Any) -> str:
    return base64.b64encode(json.dumps(value or {}).encode("utf-8")).decode("ascii")


def _sandbox_source(user_source: str) -> str:
    return f"""
const decoder = new TextDecoder();
const secrets = JSON.parse(decoder.decode(Uint8Array.from(atob(Deno.args[0]), c => c.charCodeAt(0))));
const args = JSON.parse(decoder.decode(Uint8Array.from(atob(Deno.args[1]), c => c.charCodeAt(0))));
const bytesArgs = JSON.parse(decoder.decode(Uint8Array.from(atob(Deno.args[2]), c => c.charCodeAt(0))));
let remainingQueries = Number(Deno.args[3]);
const queryTimeoutMs = Number(Deno.args[4]);
const maxUrlLength = Number(Deno.args[5]);
const maxRequestBytes = Number(Deno.args[6]);
const maxResponseBytes = Number(Deno.args[7]);

const toHex = bytes => '0x' + Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
const word = n => {{
  let x = BigInt(n);
  if (x < 0n) x = (1n << 256n) + x;
  return x.toString(16).padStart(64, '0');
}};

globalThis.Functions = {{
  encodeUint256: value => '0x' + word(value),
  encodeInt256: value => '0x' + word(value),
  encodeString: value => toHex(new TextEncoder().encode(String(value))),
  encodeBytes: value => {{
    if (typeof value === 'string' && value.startsWith('0x')) return value;
    return toHex(value);
  }},
  makeHttpRequest: async config => {{
    if (remainingQueries-- <= 0) throw new Error('too many HTTP requests');
    if (!config || !config.url || config.url.length > maxUrlLength) throw new Error('invalid request URL');
    const body = config.data === undefined ? undefined : JSON.stringify(config.data);
    if (body && new TextEncoder().encode(body).length > maxRequestBytes) throw new Error('request too large');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), queryTimeoutMs);
    try {{
      const response = await fetch(config.url, {{
        method: config.method || (body ? 'POST' : 'GET'),
        headers: config.headers || {{}},
        body,
        signal: controller.signal,
      }});
      const text = await response.text();
      if (new TextEncoder().encode(text).length > maxResponseBytes) throw new Error('response too large');
      let data = text;
      try {{ data = JSON.parse(text); }} catch {{}}
      return {{ status: response.status, statusText: response.statusText, headers: Object.fromEntries(response.headers), data }};
    }} finally {{
      clearTimeout(timeout);
    }}
  }},
}};
globalThis.secrets = secrets;
globalThis.args = args;
globalThis.bytesArgs = bytesArgs;

try {{
  const result = await (async () => {{
{user_source}
  }})();
  console.log(JSON.stringify({{ success: result || '0x' }}));
}} catch (err) {{
  console.log(JSON.stringify({{ error: {{ name: err?.name || 'Error', message: err?.message || String(err) }} }}));
}}
"""


def simulate_script(
    *,
    source: str,
    secrets: Optional[Dict[str, str]] = None,
    args: Optional[Iterable[str]] = None,
    bytesArgs: Optional[Iterable[str]] = None,
    bytes_args: Optional[Iterable[str]] = None,
    maxOnChainResponseBytes: int = DEFAULT_MAX_ON_CHAIN_RESPONSE_BYTES,
    maxExecutionTimeMs: int = DEFAULT_MAX_EXECUTION_DURATION_MS,
    maxMemoryUsageMb: int = DEFAULT_MAX_MEMORY_USAGE_MB,
    numAllowedQueries: int = DEFAULT_MAX_HTTP_REQUESTS,
    maxQueryDurationMs: int = DEFAULT_MAX_HTTP_REQUEST_DURATION_MS,
    maxQueryUrlLength: int = DEFAULT_MAX_HTTP_REQUEST_URL_LENGTH,
    maxQueryRequestBytes: int = DEFAULT_MAX_HTTP_REQUEST_BYTES,
    maxQueryResponseBytes: int = DEFAULT_MAX_HTTP_RESPONSE_BYTES,
) -> SimulationResult:
    if not isinstance(source, str):
        raise TypeError("source param is missing or invalid")
    if shutil.which("deno") is None:
        raise RuntimeError("Deno must be installed and available via PATH (`deno --version`)")

    b_args = list(bytesArgs if bytesArgs is not None else (bytes_args or []))
    if any(not isinstance(x, str) or not x.startswith("0x") for x in b_args):
        raise ValueError("bytesArgs param contains invalid hex string")

    with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False, encoding="utf-8") as fh:
        script_path = Path(fh.name)
        fh.write(_sandbox_source(source))

    try:
        proc = subprocess.run(
            [
                "deno",
                "run",
                "--no-prompt",
                f"--v8-flags=--max-old-space-size={maxMemoryUsageMb}",
                "--allow-net",
                str(script_path),
                _b64_json(secrets or {}),
                _b64_json(list(args or [])),
                _b64_json(b_args),
                str(numAllowedQueries),
                str(maxQueryDurationMs),
                str(maxQueryUrlLength),
                str(maxQueryRequestBytes),
                str(maxQueryResponseBytes),
            ],
            capture_output=True,
            text=True,
            timeout=maxExecutionTimeMs / 1000,
        )
    except subprocess.TimeoutExpired as exc:
        return SimulationResult(capturedTerminalOutput=(exc.stdout or "") + (exc.stderr or ""), errorString="script runtime exceeded")
    finally:
        try:
            script_path.unlink()
        except OSError:
            pass

    output = (proc.stdout or "") + (proc.stderr or "")
    lines = [line for line in output.splitlines() if line.strip()]
    parsed: Dict[str, Any] = {}
    captured = output
    if lines:
        try:
            parsed = json.loads(lines[-1])
            captured = "\n".join(lines[:-1])
        except json.JSONDecodeError:
            pass

    if "success" in parsed:
        response_hex = str(parsed["success"])
        if (len(response_hex.removeprefix("0x")) // 2) > maxOnChainResponseBytes:
            return SimulationResult(capturedTerminalOutput=captured, errorString=f"response >{maxOnChainResponseBytes} bytes")
        return SimulationResult(capturedTerminalOutput=captured, responseBytesHexstring=response_hex)

    if "error" in parsed:
        err = parsed["error"] or {}
        msg = err.get("message") or "script error"
        if err.get("name") == "PermissionDenied":
            msg = "attempted access to blocked resource detected"
        return SimulationResult(capturedTerminalOutput=captured, errorString=msg)

    return SimulationResult(capturedTerminalOutput=captured, errorString="syntax error, RAM exceeded, or other error")


simulateScript = simulate_script


__all__ = [
    "SimulationResult",
    "simulate_script",
    "simulateScript",
    "DEFAULT_MAX_ON_CHAIN_RESPONSE_BYTES",
    "DEFAULT_MAX_EXECUTION_DURATION_MS",
    "DEFAULT_MAX_MEMORY_USAGE_MB",
    "DEFAULT_MAX_HTTP_REQUESTS",
]
