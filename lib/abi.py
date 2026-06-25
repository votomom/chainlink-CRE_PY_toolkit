"""
Minimal ABIs for Chainlink Functions v1.x router/coordinator.

Only the parts used by this utility (cost estimation, timeouts,
commitments, response events). Sourced from FunctionsRouter and
FunctionsCoordinator in `smartcontractkit/chainlink` v1_0_0.
"""

from __future__ import annotations


COMMITMENT_TUPLE_COMPONENTS = [
    {"name": "requestId", "type": "bytes32"},
    {"name": "coordinator", "type": "address"},
    {"name": "estimatedTotalCostJuels", "type": "uint96"},
    {"name": "client", "type": "address"},
    {"name": "subscriptionId", "type": "uint64"},
    {"name": "callbackGasLimit", "type": "uint32"},
    {"name": "adminFee", "type": "uint72"},
    {"name": "donFee", "type": "uint72"},
    {"name": "gasOverheadBeforeCallback", "type": "uint40"},
    {"name": "gasOverheadAfterCallback", "type": "uint40"},
    {"name": "timeoutTimestamp", "type": "uint32"},
]


ROUTER_ABI = [
    {
        "inputs": [],
        "name": "getAllowListId",
        "outputs": [{"name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "id", "type": "bytes32"}],
        "name": "getContractById",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "subscriptionId", "type": "uint64"},
            {"name": "callbackGasLimit", "type": "uint32"},
        ],
        "name": "isValidCallbackGasLimit",
        "outputs": [],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "subscriptionId", "type": "uint64"}],
        "name": "getSubscription",
        "outputs": [
            {
                "name": "",
                "type": "tuple",
                "components": [
                    {"name": "balance", "type": "uint96"},
                    {"name": "owner", "type": "address"},
                    {"name": "blockedBalance", "type": "uint96"},
                    {"name": "proposedOwner", "type": "address"},
                    {"name": "consumers", "type": "address[]"},
                    {"name": "flags", "type": "bytes32"},
                ],
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "createSubscription",
        "outputs": [{"name": "subscriptionId", "type": "uint64"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "consumer", "type": "address"}],
        "name": "createSubscriptionWithConsumer",
        "outputs": [{"name": "subscriptionId", "type": "uint64"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "subscriptionId", "type": "uint64"},
            {"name": "consumer", "type": "address"},
        ],
        "name": "addConsumer",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "subscriptionId", "type": "uint64"},
            {"name": "consumer", "type": "address"},
        ],
        "name": "removeConsumer",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "subscriptionId", "type": "uint64"},
            {"name": "to", "type": "address"},
        ],
        "name": "cancelSubscription",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "subscriptionId", "type": "uint64"},
            {"name": "newOwner", "type": "address"},
        ],
        "name": "proposeSubscriptionOwnerTransfer",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "subscriptionId", "type": "uint64"}],
        "name": "acceptSubscriptionOwnerTransfer",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {
                "name": "requestsToTimeoutByCommitment",
                "type": "tuple[]",
                "components": COMMITMENT_TUPLE_COMPONENTS,
            }
        ],
        "name": "timeoutRequests",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "anonymous": False,
        "name": "RequestProcessed",
        "type": "event",
        "inputs": [
            {"indexed": True, "name": "requestId", "type": "bytes32"},
            {"indexed": True, "name": "subscriptionId", "type": "uint64"},
            {"indexed": False, "name": "totalCostJuels", "type": "uint96"},
            {"indexed": False, "name": "transmitter", "type": "address"},
            {"indexed": False, "name": "resultCode", "type": "uint8"},
            {"indexed": False, "name": "response", "type": "bytes"},
            {"indexed": False, "name": "err", "type": "bytes"},
            {"indexed": False, "name": "callbackReturnData", "type": "bytes"},
        ],
    },
    {
        "anonymous": False,
        "name": "RequestStart",
        "type": "event",
        "inputs": [
            {"indexed": True, "name": "requestId", "type": "bytes32"},
            {"indexed": True, "name": "donId", "type": "bytes32"},
            {"indexed": True, "name": "subscriptionId", "type": "uint64"},
            {"indexed": False, "name": "subscriptionOwner", "type": "address"},
            {"indexed": False, "name": "requestingContract", "type": "address"},
            {"indexed": False, "name": "requestInitiator", "type": "address"},
            {"indexed": False, "name": "data", "type": "bytes"},
            {"indexed": False, "name": "dataVersion", "type": "uint16"},
            {"indexed": False, "name": "callbackGasLimit", "type": "uint32"},
            {"indexed": False, "name": "estimatedTotalCostJuels", "type": "uint96"},
        ],
    },
]


LINK_TOKEN_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "data", "type": "bytes"},
        ],
        "name": "transferAndCall",
        "outputs": [{"name": "success", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


ALLOWLIST_ABI = [
    {
        "inputs": [
            {"name": "sender", "type": "address"},
            {"name": "proof", "type": "bytes32[]"},
        ],
        "name": "hasAccess",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    }
]


COORDINATOR_ABI = [
    {
        "inputs": [],
        "name": "getThresholdPublicKey",
        "outputs": [{"name": "", "type": "bytes"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getDONPublicKey",
        "outputs": [{"name": "", "type": "bytes"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "subscriptionId", "type": "uint64"},
            {"name": "data", "type": "bytes"},
            {"name": "callbackGasLimit", "type": "uint32"},
            {"name": "gasPriceWei", "type": "uint256"},
        ],
        "name": "estimateCost",
        "outputs": [{"name": "", "type": "uint96"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "anonymous": False,
        "name": "OracleRequest",
        "type": "event",
        "inputs": [
            {"indexed": True, "name": "requestId", "type": "bytes32"},
            {"indexed": True, "name": "requestingContract", "type": "address"},
            {"indexed": False, "name": "requestInitiator", "type": "address"},
            {"indexed": False, "name": "subscriptionId", "type": "uint64"},
            {"indexed": False, "name": "subscriptionOwner", "type": "address"},
            {"indexed": False, "name": "data", "type": "bytes"},
            {"indexed": False, "name": "dataVersion", "type": "uint16"},
            {"indexed": False, "name": "flags", "type": "bytes32"},
            {"indexed": False, "name": "callbackGasLimit", "type": "uint64"},
            {
                "indexed": False,
                "name": "commitment",
                "type": "tuple",
                "components": COMMITMENT_TUPLE_COMPONENTS,
            },
        ],
    },
    {
        "anonymous": False,
        "name": "OracleResponse",
        "type": "event",
        "inputs": [
            {"indexed": True, "name": "requestId", "type": "bytes32"},
            {"indexed": False, "name": "transmitter", "type": "address"},
        ],
    },
]


def format_bytes32_string(value: str) -> bytes:
    raw = value.encode("utf-8")
    if len(raw) > 32:
        raise ValueError("value does not fit in bytes32")
    return raw + b"\x00" * (32 - len(raw))
