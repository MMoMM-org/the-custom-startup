"""Pydantic v2 fixture — BaseModel with Field(default=…, description="…")."""
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """Application configuration settings."""

    host: str = Field(default="localhost", description="Hostname to bind the server to")
    port: int = Field(default=8080, description="TCP port number for the HTTP listener")
