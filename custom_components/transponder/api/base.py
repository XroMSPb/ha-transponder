"""Common data model and base class for transponder providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class TransponderError(Exception):
    """Base error for transponder clients."""


class TransponderAuthError(TransponderError):
    """Raised when credentials are rejected."""


class TransponderConnectionError(TransponderError):
    """Raised when the provider is unreachable or replies unexpectedly."""


@dataclass(slots=True)
class Account:
    """A single billing account / contract with its balance.

    ``account_id`` must be unique and stable within a provider – it forms the
    entity/device identity.
    """

    provider: str
    account_id: str
    balance: float | None
    currency: str = "RUB"
    name: str | None = None
    contract: str | None = None
    status: str | None = None
    updated_at: str | None = None
    bonus_points: float | None = None
    transponders_count: int | None = None
    topup_url: str | None = None
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def unique_key(self) -> str:
        """Provider-scoped unique key for this account."""
        return f"{self.provider}_{self.account_id}"


class TransponderClient(ABC):
    """Interface every provider client implements."""

    provider: str

    @abstractmethod
    async def async_get_accounts(self) -> list[Account]:
        """Log in if needed and return the current balances."""
