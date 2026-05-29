# Session Summary: Refactoring `simple-FastAPI-app` Toward Dispatch Conventions

This session focused on understanding how the small `simple-FastAPI-app` could be refactored to follow the organization style used by the larger `dispatch` repository without copying Dispatch's full production stack.

The main outcome: the app was split from a single `main.py` into a package under `src/simple_fastapi_app`, with separate modules for app startup, API routing, item route handlers, service/database logic, config, and tests.

## Starting Point

The app originally had most concerns mixed together in one root-level `main.py`:

```python
from fastapi import FastAPI, Path, Query, HTTPException
from pydantic import BaseModel
import psycopg

DATABASE_URL = "postgresql://percy:1144simplefast@localhost:5433/fastapi_app_db"

def get_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

class Item(BaseModel):
    name: str
    number: int

app = FastAPI()
```

That worked, but it mixed these responsibilities:

- App creation
- Route registration
- Request validation models
- Database connection setup
- SQL queries
- Business behavior

This is fine for a first FastAPI experiment, but it gets hard to maintain as the app grows.

## Dispatch Conventions We Borrowed

The larger `dispatch` repo uses a repeated module pattern:

```text
resource/
  models.py
  service.py
  views.py
```

In Dispatch:

- `main.py` creates and configures the FastAPI app.
- `api.py` creates central routers and includes resource routers.
- `views.py` defines HTTP endpoints.
- `service.py` contains business logic and database operations.
- `models.py` contains SQLAlchemy and Pydantic models.
- `database/core.py` contains shared database setup.
- `config.py` reads configuration from environment variables.

For this learning app, we copied the shape, not the whole production complexity.

## Current Target Structure

The app now follows this structure:

```text
simple-FastAPI-app/
  pyproject.toml
  README.md
  compose.yaml
  src/
    simple_fastapi_app/
      __init__.py
      main.py
      api.py
      config.py
      database/
        __init__.py
        core.py
      item/
        __init__.py
        models.py
        service.py
        views.py
  tests/
    test_health.py
    test_get.py
    test_post.py
    test_all.py
```

The placeholder item tests still need to be implemented.

## Refactor Steps

### 1. Add Tests First

We started with a health test:

```python
from fastapi.testclient import TestClient
from simple_fastapi_app.main import app


def test_health():
    client = TestClient(app)

    response = client.get("/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

Key idea: tests give you a checkpoint while refactoring. If behavior breaks, you know immediately.

### 2. Create A Package Layout

The app was moved under `src/simple_fastapi_app`.

This is called a `src` layout. It helps avoid accidentally importing files from the project root instead of the installed package.

### 3. Move App Creation Into `main.py`

Current app entrypoint:

```python
from fastapi import FastAPI

from simple_fastapi_app.api import api_router


app = FastAPI()
app.include_router(api_router)
```

Important fix made during the session:

```python
from simple_fastapi_app.main import app
```

This line was accidentally placed inside `simple_fastapi_app/main.py`, causing a circular import. It was removed.

### 4. Add A Central Router In `api.py`

The central router wires together top-level routes and resource routers:

```python
from fastapi import APIRouter

from simple_fastapi_app.item.views import router as item_router


api_router = APIRouter()


@api_router.get("/health/")
def get_health():
    return {"status": "ok"}


api_router.include_router(item_router, prefix="/items", tags=["items"])
```

This keeps `main.py` small. `main.py` creates the app; `api.py` decides what routes are included.

### 5. Move Item Routes Into `item/views.py`

The item routes now live in their own resource module:

```python
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from simple_fastapi_app.item.models import Item
from simple_fastapi_app.item import service


router = APIRouter()


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: Annotated[str, Path(max_length=10)]):
    item = service.get_item(item_id=item_id)

    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    return item


@router.put("/{item_id}", response_model=Item)
def upsert_item(
    item_id: Annotated[str, Path(max_length=10)],
    other: Annotated[int, Query(ge=1144)],
):
    return service.upsert_item(item_id=item_id, number=other)


@router.get("", response_model=dict[str, Item])
def get_all_items():
    return service.get_all_items()
```

The route names were also improved:

```text
Old: GET  /getitem/{item_id}
New: GET  /items/{item_id}

Old: POST /postitem/{item_id}
New: PUT  /items/{item_id}

Old: GET  /all
New: GET  /items
```

### 6. Move Database Logic Into `item/service.py`

The service layer owns SQL and database behavior:

```python
from simple_fastapi_app.database.core import get_connection


def get_item(*, item_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, number FROM items WHERE id = %s",
                (item_id,),
            )
            return cur.fetchone()
```

For inserting or updating:

```python
def upsert_item(*, item_id: str, number: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO items (id, name, number)
                VALUES (%s, %s, %s)
                ON CONFLICT (id)
                DO UPDATE SET number = EXCLUDED.number
                """,
                (item_id, item_id, number),
            )

    return {"name": item_id, "number": number}
```

Key idea: route handlers should usually be thin. They should parse HTTP input, call services, and translate errors into HTTP responses.

### 7. Move Models And Config Out Of `main.py`

Pydantic models now live in `item/models.py`:

```python
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class Item(BaseModel):
    name: str
    number: int
```

Config now reads from the environment:

```python
import os


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://percy:1144simplefast@localhost:5433/fastapi_app_db",
)
```

Database connection setup now lives in `database/core.py`:

```python
import psycopg
from psycopg.rows import dict_row

from simple_fastapi_app.config import DATABASE_URL


def get_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)
```

### 8. Add `pyproject.toml`

The app now has package metadata and test configuration:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "simple-fastapi-app"
version = "0.1.0"
description = "A small FastAPI learning app"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "fastapi",
    "pydantic",
    "psycopg[binary]",
    "uvicorn",
]

[project.optional-dependencies]
dev = [
    "httpx",
    "pytest",
]

[tool.hatch.build.targets.wheel]
packages = ["src/simple_fastapi_app"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

The app can be installed in editable mode:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Then imports work normally:

```python
from simple_fastapi_app.main import app
```

## Problems Found And Fixed

### Circular Import

Problem:

```python
from simple_fastapi_app.main import app
```

This was inside `simple_fastapi_app/main.py`, so the module tried to import itself before it finished loading.

Fix:

```python
from fastapi import FastAPI
from simple_fastapi_app.api import api_router

app = FastAPI()
app.include_router(api_router)
```

### Broken Test Import

Problem:

```python
from main import app
```

This no longer worked because the root `main.py` was deleted.

Correct import:

```python
from simple_fastapi_app.main import app
```

### README Encoding Problem

Editable install failed because `README.md` was UTF-16 LE, starting with bytes:

```text
FF FE
```

Hatchling expects UTF-8 for the README.

Fix used:

```powershell
$readme = (Resolve-Path -LiteralPath .\README.md).ProviderPath
$content = [System.IO.File]::ReadAllText($readme, [System.Text.Encoding]::Unicode)
$utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList $false
[System.IO.File]::WriteAllText($readme, $content, $utf8NoBom)
```

After conversion, the file started with:

```text
23 20 73 69
```

That corresponds to:

```text
# si
```

## Verified Working State

The following checks passed:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m compileall src tests
```

The test suite currently reports:

```text
1 passed
```

The app imports successfully:

```powershell
.\.venv\Scripts\python.exe -c "from simple_fastapi_app.main import app; print(app.title)"
```

The registered routes include:

```text
/health/
/items/{item_id}
/items
```

The running Postgres container was verified:

```powershell
docker compose ps
```

Manual `TestClient` checks passed:

```text
GET /health/                  -> 200 {"status": "ok"}
PUT /items/verify?other=1144  -> 200
GET /items/verify             -> 200
GET /items                    -> 200
GET /items/nope               -> 404
PUT /items/verify?other=1     -> 422
```

## Key Concepts

### Separation Of Concerns

Each file should have a clear job:

```text
main.py        Creates the FastAPI app
api.py         Wires routers together
views.py       Defines HTTP endpoints
service.py     Contains business/database logic
models.py      Contains request/response schemas
config.py      Reads settings
database/core.py  Creates database connections
```

### Thin Route Handlers

A route should usually look like this:

```python
@router.get("/{item_id}", response_model=Item)
def get_item(item_id: str):
    item = service.get_item(item_id=item_id)

    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    return item
```

The route handles HTTP. The service handles the actual work.

### `src` Layout

The `src` layout helps ensure your tests import the real package:

```text
src/simple_fastapi_app/
```

With this layout, avoid imports like:

```python
from src.simple_fastapi_app.main import app
```

Use:

```python
from simple_fastapi_app.main import app
```

### Editable Installs

Editable installs make local development easier:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

After that, changes to files under `src/simple_fastapi_app` are reflected without reinstalling.

### FastAPI Validation

This route parameter:

```python
item_id: Annotated[str, Path(max_length=10)]
```

means `item_id` cannot be longer than 10 characters.

This query parameter:

```python
other: Annotated[int, Query(ge=1144)]
```

means `other` must be an integer greater than or equal to `1144`.

FastAPI automatically returns `422` when validation fails.

### SQL Parameterization

This is good:

```python
cur.execute(
    "SELECT name, number FROM items WHERE id = %s",
    (item_id,),
)
```

This helps prevent SQL injection. Avoid building SQL with f-strings:

```python
# Avoid this
cur.execute(f"SELECT name FROM items WHERE id = '{item_id}'")
```

## Suggested Next Improvements

### 1. Implement The Placeholder Tests

Add real tests for:

```text
tests/test_get.py
tests/test_post.py
tests/test_all.py
```

Example for a mocked service-level route test:

```python
from fastapi.testclient import TestClient

from simple_fastapi_app.main import app


def test_get_missing_item():
    client = TestClient(app)

    response = client.get("/items/nope")

    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found"}
```

This test currently depends on the real database. A later improvement would be to isolate tests from the real Postgres container.

### 2. Add A `.gitignore`

Useful entries:

```gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
dist/
build/
*.egg-info/
```

### 3. Add A Database Initialization Script

Right now, the app assumes the `items` table already exists.

You could add a script or migration that creates:

```sql
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    number INTEGER NOT NULL
);
```

### 4. Add SQLAlchemy Later

Do not rush this. The current `psycopg` version is useful for learning SQL directly.

When ready, introduce SQLAlchemy in stages:

1. Add `engine` and `SessionLocal`.
2. Add `Base`.
3. Create an `Item` SQLAlchemy model.
4. Convert one service function at a time.
5. Add Alembic migrations after the model is stable.

Example shape:

```python
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from simple_fastapi_app.config import DATABASE_URL


engine = create_engine(DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://"))
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()


DbSession = Annotated[Session, Depends(get_db)]
```

### 5. Add Better Configuration

Eventually, consider using Pydantic settings:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str


settings = Settings()
```

For now, `os.environ.get()` is simple and understandable.

### 6. Improve API Naming

Current routes:

```text
GET /items
GET /items/{item_id}
PUT /items/{item_id}
```

This is already much better than:

```text
/getitem/{item_id}
/postitem/{item_id}
/all
```

Later, consider using request bodies instead of query parameters for item creation:

```python
class ItemCreate(BaseModel):
    name: str
    number: int
```

Then:

```python
@router.put("/{item_id}", response_model=Item)
def upsert_item(item_id: str, item_in: ItemCreate):
    ...
```

### 7. Learn Dependency Injection

FastAPI dependency injection is one of its most important concepts.

Current version:

```python
def get_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)
```

Future version:

```python
def get_db():
    with get_connection() as conn:
        yield conn
```

Then routes can request it:

```python
from typing import Annotated
from fastapi import Depends


DbConnection = Annotated[object, Depends(get_db)]
```

## Learning Strategy

Use this order to build knowledge:

1. FastAPI routing and validation
2. Pydantic request and response models
3. HTTP methods and REST naming
4. SQL basics with `psycopg`
5. Tests with `TestClient`
6. Environment-based config
7. Package structure and imports
8. Dependency injection
9. SQLAlchemy ORM
10. Alembic migrations
11. Authentication
12. Background jobs and production deployment

Avoid trying to learn all of Dispatch at once. Dispatch includes production concerns such as auth, plugins, multi-tenant schemas, frontend mounting, metrics, Sentry, and rate limiting. Those are useful later, but they are distractions while learning core backend structure.

## Useful Commands

Install the app:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Run the app:

```powershell
.\.venv\Scripts\python.exe -m uvicorn simple_fastapi_app.main:app --reload
```

Check Postgres:

```powershell
docker compose ps
```

Start Postgres:

```powershell
docker compose up -d
```

Check registered routes quickly:

```powershell
.\.venv\Scripts\python.exe -c "from simple_fastapi_app.main import app; print([route.path for route in app.routes])"
```

## Final State

The app is now organized more like a real backend project:

- Package lives under `src/`.
- FastAPI app imports correctly.
- Editable install works.
- README encoding is fixed.
- Health test passes.
- Database-backed routes work manually.
- The app follows a small version of Dispatch's module conventions.

The next best improvement is to turn the manual item route checks into real pytest tests.
