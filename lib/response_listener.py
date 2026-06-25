from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .listener import (
    listen_for_response,
    listen_for_response_from_tx,
)
from .web3_helpers import make_w3


class ResponseListener:
    def __init__(
        self,
        *,
        provider: Optional[Any] = None,
        rpc_url: Optional[str] = None,
        functionsRouterAddress: Optional[str] = None,
        functions_router_address: Optional[str] = None,
    ) -> None:
        self.provider = provider or (make_w3(rpc_url) if rpc_url else None)
        if self.provider is None:
            raise ValueError("provider or rpc_url is required")
        self.functionsRouterAddress = functionsRouterAddress or functions_router_address
        if not self.functionsRouterAddress:
            raise ValueError("functionsRouterAddress is required")
        self._stopped = False

    def listenForResponse(self, requestId: str, timeoutMs: int = 300_000) -> Dict[str, Any]:
        self._stopped = False
        return listen_for_response(
            w3=self.provider,
            functions_router_address=self.functionsRouterAddress,
            request_id=requestId,
            timeout_s=timeoutMs / 1000,
        )

    def listenForResponseFromTransaction(
        self,
        txHash: str,
        timeoutMs: int = 3_000_000,
        confirmations: int = 1,
        checkIntervalMs: int = 2_000,
    ) -> Dict[str, Any]:
        self._stopped = False
        return listen_for_response_from_tx(
            w3=self.provider,
            functions_router_address=self.functionsRouterAddress,
            tx_hash=txHash,
            timeout_s=timeoutMs / 1000,
            confirmations=confirmations,
            poll_interval_s=checkIntervalMs / 1000,
        )

    def listenForResponses(
        self,
        subscriptionId: int | str,
        callback: Callable[[Dict[str, Any]], Any],
        checkIntervalMs: int = 2_000,
    ) -> None:
        from .abi import ROUTER_ABI
        from .listener import FulfillmentCode, _format_response
        from .web3_helpers import require_web3

        Web3 = require_web3()
        router = self.provider.eth.contract(
            address=Web3.to_checksum_address(self.functionsRouterAddress),
            abi=ROUTER_ABI,
        )
        event_filter = router.events.RequestProcessed.create_filter(
            from_block=self.provider.eth.block_number,
            argument_filters={"subscriptionId": int(subscriptionId)},
        )
        self._stopped = False

        import time

        while not self._stopped:
            for ev in event_filter.get_new_entries():
                args = ev["args"]
                if args["resultCode"] == FulfillmentCode.INVALID_REQUEST_ID:
                    continue
                callback(_format_response(args))
            time.sleep(checkIntervalMs / 1000)

    def stopListeningForResponses(self) -> None:
        self._stopped = True


__all__ = ["ResponseListener"]
