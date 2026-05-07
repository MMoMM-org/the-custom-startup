"""Plain @dataclass fixture with no class-level docstring — all fields → [NEEDS DESCRIPTION]."""
from dataclasses import dataclass


@dataclass
class CacheConfig:
    backend: str = "memory"
    ttl: int = 300
    max_size: int = 1000
