# Python Project Patterns Reference

## pyproject.toml — Complete Template

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "my-project"
version = "0.1.0"
description = "A short description"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "mypy>=1.10",
    "ruff>=0.4",
]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "UP",   # pyupgrade
    "SIM",  # flake8-simplify
    "RUF",  # ruff-native rules
]
ignore = ["E501"]  # line length handled by formatter

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
strict = true
python_version = "3.11"
ignore_missing_imports = false

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "--cov=src --cov-report=term-missing --cov-fail-under=80"

[tool.coverage.run]
source = ["src"]
omit = ["tests/*", "src/*/migrations/*"]
```

---

## Virtual Environment Setup

```bash
# Create venv in repo root (always — never pip install --break-system-packages)
python -m venv venv
source venv/bin/activate

# Install project with dev deps
pip install -e ".[dev]"

# Verify
python -m ruff --version
python -m mypy --version
python -m pytest --version
```

`.gitignore` must include:
```
venv/
.venv/
__pycache__/
*.pyc
.mypy_cache/
.ruff_cache/
.pytest_cache/
*.egg-info/
dist/
```

---

## Module Layout

```
my-project/
├── src/
│   └── my_project/
│       ├── __init__.py       # public API exports
│       ├── models.py         # Pydantic models / dataclasses
│       ├── services.py       # business logic
│       ├── repositories.py   # data access
│       ├── config.py         # settings (pydantic-settings)
│       └── exceptions.py     # custom exception hierarchy
├── tests/
│   ├── conftest.py           # shared fixtures
│   ├── unit/
│   └── integration/
├── pyproject.toml
└── README.md
```

`src/` layout prevents accidental imports of the package without installation — enforces clean boundaries.

---

## Type Hints

### Function Signatures

```python
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")

# WRONG — missing return type, missing arg types
def get_users(limit):
    return db.query(limit)

# CORRECT
def get_users(limit: int = 10) -> list[User]:
    return db.query(limit)

# Generic function
def first(items: Sequence[T]) -> T | None:
    return items[0] if items else None
```

### Pydantic v2 Models

```python
from pydantic import BaseModel, Field, field_validator

class CreateUserRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r"^[^@]+@[^@]+\.[^@]+$")
    age: int = Field(ge=0, le=150)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()

class User(BaseModel):
    model_config = {"frozen": True}   # immutable after creation

    id: int
    name: str
    email: str
```

### Dataclasses for Simpler Value Objects

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Money:
    amount: int      # cents
    currency: str

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError(f"amount must be non-negative, got {self.amount}")
```

---

## Error Handling

```python
# Custom exception hierarchy
class AppError(Exception):
    """Base class for application errors."""

class NotFoundError(AppError):
    def __init__(self, resource: str, id: str | int) -> None:
        super().__init__(f"{resource} {id} not found")
        self.resource = resource
        self.id = id

class ValidationError(AppError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"validation: {field} {message}")
        self.field = field

# WRONG — bare except
try:
    result = process(data)
except:               # catches KeyboardInterrupt, SystemExit — never do this
    pass

# WRONG — too broad
try:
    result = process(data)
except Exception:
    pass              # swallowed — nothing logged, caller has no idea

# CORRECT
try:
    result = process(data)
except NotFoundError:
    return None       # expected case, caller can handle
except (TypeError, ValueError) as exc:
    raise ValidationError("data", str(exc)) from exc
```

---

## Mutable Default Arguments

```python
# WRONG — list is shared across all calls
def append_item(item: str, items: list[str] = []) -> list[str]:
    items.append(item)
    return items

# CORRECT — use None sentinel
def append_item(item: str, items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append(item)
    return items
```

---

## Logging

```python
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Setup once at entry point (NOT in library code)
def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

# For structured JSON logging in production: use structlog
import structlog

log = structlog.get_logger()

async def handle_request(user_id: int, action: str) -> None:
    log.info("handling request", user_id=user_id, action=action)
    try:
        result = await process(user_id, action)
        log.info("request completed", user_id=user_id, result=result)
    except AppError as exc:
        log.warning("request failed", user_id=user_id, error=str(exc))
        raise
```

---

## Async Patterns

```python
import asyncio
import httpx

# Concurrent requests — NOT sequential awaits in a loop
async def fetch_all(urls: list[str]) -> list[httpx.Response]:
    async with httpx.AsyncClient() as client:
        return await asyncio.gather(*(client.get(url) for url in urls))

# Timeout any coroutine
async def with_timeout(coro: Any, seconds: float) -> Any:
    return await asyncio.wait_for(coro, timeout=seconds)

# Limit concurrency with semaphore
sem = asyncio.Semaphore(10)

async def fetch_limited(client: httpx.AsyncClient, url: str) -> httpx.Response:
    async with sem:
        return await client.get(url)
```

---

## pytest Conventions

```python
# tests/conftest.py
import pytest
from my_project.config import Settings

@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(database_url="sqlite:///test.db", debug=True)

@pytest.fixture
def db(settings: Settings):
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)

# tests/unit/test_user_service.py
class TestCreateUser:
    def test_creates_user_with_valid_data(self, db: Session) -> None:
        service = UserService(db)
        user = service.create(name="Alice", email="alice@example.com")
        assert user.id is not None
        assert user.name == "Alice"

    def test_raises_on_duplicate_email(self, db: Session) -> None:
        service = UserService(db)
        service.create(name="Alice", email="alice@example.com")
        with pytest.raises(ValidationError, match="email already exists"):
            service.create(name="Bob", email="alice@example.com")

    @pytest.mark.parametrize("email", ["", "not-an-email", "@nodomain"])
    def test_rejects_invalid_emails(self, db: Session, email: str) -> None:
        with pytest.raises(ValidationError):
            UserService(db).create(name="Test", email=email)
```

---

## Settings with pydantic-settings

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    log_level: str = "INFO"
    debug: bool = False
    max_connections: int = 10
    secret_key: str  # required — startup fails if not set

# Singleton via module-level instance (never re-parse in tests)
settings = Settings()
```

---

## Anti-Patterns

| Anti-pattern | Problem | Fix |
|---|---|---|
| `pip install --break-system-packages` | Corrupts system Python (PEP 668) | Always use `venv` |
| Bare `except:` | Catches `KeyboardInterrupt`, `SystemExit` | Catch specific exception types |
| `def f(items=[])` mutable default | Shared state across calls | Use `None` sentinel |
| `from module import *` | Pollutes namespace, breaks type checking | Explicit imports |
| `print()` for logging | No level, no context, hard to filter | `logging` / `structlog` |
| Hard-coded config values | Not deployable | `pydantic-settings` + env vars |
| `os.environ["KEY"]` scattered | KeyError on missing, no validation | Parse all env in `Settings` at startup |
| Missing `__all__` in library | Leaks internal names | Define `__all__` in `__init__.py` |
