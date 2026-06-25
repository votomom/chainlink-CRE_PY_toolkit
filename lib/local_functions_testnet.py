from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Optional


SIMULATED_DON_ID = "local-functions-testnet"
SIMULATED_ALLOW_LIST_ID = "allowlist"


@dataclass(frozen=True)
class LocalFunctionsTestnetUnavailable:
    reason: str


def start_local_functions_testnet(simulationConfigPath: Optional[str] = None, port: int = 8545):
    """
    Compatibility entrypoint for toolkit's `startLocalFunctionsTestnet`.

    The JS toolkit bundles compiled Chainlink contract bytecode. This Python
    package intentionally does not vendor those large generated artifacts yet,
    so full local router/coordinator deployment is not available here.
    """
    if shutil.which("anvil") is None:
        raise RuntimeError("Anvil is required for localFunctionsTestnet (`anvil --version` must work)")
    raise NotImplementedError(
        "startLocalFunctionsTestnet requires bundled Chainlink contract bytecode. "
        "Use simulate_script() for local JS execution, or run the Node toolkit local testnet."
    )


def deploy_functions_oracle(*args, **kwargs):
    raise NotImplementedError(
        "deployFunctionsOracle requires bundled Chainlink contract bytecode and is not available in this Python build"
    )


startLocalFunctionsTestnet = start_local_functions_testnet
deployFunctionsOracle = deploy_functions_oracle


__all__ = [
    "SIMULATED_DON_ID",
    "SIMULATED_ALLOW_LIST_ID",
    "LocalFunctionsTestnetUnavailable",
    "start_local_functions_testnet",
    "startLocalFunctionsTestnet",
    "deploy_functions_oracle",
    "deployFunctionsOracle",
]
