"""Pydantic config for multi-source fixture."""
from dataclasses import dataclass


@dataclass
class ServerConfig:
    """Server configuration.

    Attributes:
        host: Server hostname.
        port: Server port.
    """

    host: str = "localhost"
    port: int = 9000
