"""Core value types."""

import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class Transaction:
    date: datetime.date
    amount: float
    currency: str
    category: str
    description: str = ""
