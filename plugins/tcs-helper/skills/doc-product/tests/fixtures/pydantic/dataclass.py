"""Plain @dataclass fixture with class-level defaults and Google-style docstring."""
from dataclasses import dataclass


@dataclass
class DatabaseConfig:
    """Database connection configuration.

    Attributes:
        url: Connection URL for the database.
        pool_size: Number of connections to keep in the pool.
        timeout: Query timeout in seconds.
    """

    url: str = "sqlite:///app.db"
    pool_size: int = 5
    timeout: float = 30.0
