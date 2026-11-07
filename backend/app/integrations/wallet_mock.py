"""Billetera simulada persistente.

No implementa un contrato de Yape. Solo demuestra el puerto ``WalletGateway``
con estados deterministas y sin llamadas externas.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class WalletOperation:
    operation_id: str
    kind: str
    amount: str
    status: str = "ACCEPTED"
    metadata: dict = field(default_factory=dict)


class WalletMock:
    def request_payment(self, amount: str, reference: str) -> WalletOperation:
        return WalletOperation(
            operation_id=f"demo-pay-{uuid.uuid4().hex[:12]}",
            kind="PAYMENT",
            amount=amount,
            metadata={"reference": reference, "simulated": True},
        )

    def request_transfer(self, amount: str, direction: str) -> WalletOperation:
        return WalletOperation(
            operation_id=f"demo-trx-{uuid.uuid4().hex[:12]}",
            kind=direction,
            amount=amount,
            metadata={"simulated": True},
        )

    def get_status(self, operation_id: str) -> WalletOperation:
        return WalletOperation(
            operation_id=operation_id,
            kind="UNKNOWN",
            amount="0.00",
            status="SIMULATED",
            metadata={"simulated": True},
        )


wallet = WalletMock()
