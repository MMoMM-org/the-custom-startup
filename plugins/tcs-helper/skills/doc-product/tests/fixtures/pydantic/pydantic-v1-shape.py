"""Pydantic v1-shaped fixture — BaseModel with plain annotations and class-level defaults."""
from pydantic import BaseModel


class ServerConfig(BaseModel):
    """Server configuration."""

    host: str = "0.0.0.0"
    port: int = 9000
    debug: bool = False
