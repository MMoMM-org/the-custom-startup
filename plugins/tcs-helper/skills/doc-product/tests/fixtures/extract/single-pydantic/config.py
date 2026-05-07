"""Dataclass fixture for extract detection."""
from dataclasses import dataclass


@dataclass
class AppConfig:
    """Application configuration.

    Attributes:
        debug: Enable debug mode.
        workers: Number of worker threads.
    """

    debug: bool = False
    workers: int = 4
