# FastAPI, Docker Compose, and Local Postgres Session Summary

This note summarizes the work from this session: replacing an in-memory Python dictionary in a simple FastAPI app with a local Postgres database running in Docker Compose.

The goal was learning-oriented: understand the moving pieces, convert the routes one at a time, and debug the errors that came up.

## Starting Point

The app originally stored items in memory:

```python
data = {}
```

The important routes were:

```python
@app.post("/postitem/{item_id}", response_model=Item)
async def post_item(...):
    i = Item(name=item_id, number=other)
    data[item_id] = i
    return {"name": item_id, "number": other}
```

```python
@app.get("/getitem/{item_id}", response_model=Item)
async def get_item(...):
    if item_id not in data:
        raise HTTPException(status_code=404, detail="Item not found")

    i = data[item_id]
    return {"name": i.name, "number": i.number}
```

```python
@app.get("/all", response_model=dict[str, Item])
async def get_all():
    return data
```

That works while the app is running, but the data disappears when the Python process restarts.

## Final Local Database Setup

The project now uses a Postgres container from Docker Compose.

Current `compose.yaml` shape:

```yaml
services:
  postgres:
    image: postgres:16
    container_name: simple-fastapi-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: percy
      POSTGRES_PASSWORD: 1144simplefast
      POSTGRES_DB: fastapi_app_db
    ports:
      - "5433:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

Important idea:

```text
localhost:5433 on Windows -> port 5432 inside the Postgres container
```

The app connects with:

```python
DATABASE_URL = "postgresql://percy:1144simplefast@localhost:5433/fastapi_app_db"
```

The port is `5433` because there was already a Windows Postgres process listening on `5432`.

## Useful Docker Commands

Start Postgres:

```powershell
docker compose up -d
```

Check container status:

```powershell
docker compose ps
```

Stop Postgres but keep the database volume:

```powershell
docker compose down
```

Stop Postgres and delete the database volume:

```powershell
docker compose down -v
```

Use `down -v` only when you want to delete local database data and start fresh.

## Database Table

The app stores items in a table called `items`.

```sql
CREATE TABLE items (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    number INTEGER NOT NULL
);
```

Connect to Postgres inside the container:

```powershell
docker compose exec postgres psql -U percy -d fastapi_app_db
```

Check tables:

```sql
\dt
```

Exit `psql`:

```sql
\q
```

## Python Database Driver

The app uses `psycopg`, the modern Psycopg 3 package.

Install:

```powershell
pip install "psycopg[binary]"
```

Imports:

```python
import psycopg
from psycopg.rows import dict_row
```

Connection helper:

```python
def get_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)
```

The `dict_row` row factory makes query results behave like dictionaries:

```python
row["name"]
row["number"]
```

Without `dict_row`, rows are more tuple-like.

## Route Conversion: POST

The old in-memory idea:

```python
data[item_id] = i
```

The database idea:

```sql
INSERT INTO items (id, name, number)
VALUES (...)
```

Working route pattern:

```python
@app.post("/postitem/{item_id}", response_model=Item)
async def post_item(
    item_id: Annotated[str, Path(max_length=10)],
    other: Annotated[int, Query(ge=1144)]
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO items (id, name, number)
                VALUES (%s, %s, %s)
                ON CONFLICT (id)
                DO UPDATE SET number = EXCLUDED.number
                """,
                (item_id, item_id, other)
            )

    return {"name": item_id, "number": other}
```

Key detail:

```python
VALUES (%s, %s, %s)
```

This is valid SQL. This is not:

```python
VALUES %s %s %s
```

## Route Conversion: GET One Item

The old in-memory idea:

```python
if item_id not in data:
    raise HTTPException(status_code=404, detail="Item not found")

i = data[item_id]
```

The database idea:

```sql
SELECT name, number
FROM items
WHERE id = ...
```

Working route pattern:

```python
@app.get("/getitem/{item_id}", response_model=Item, responses={404: {"description": "Item not found"}})
async def get_item(item_id: Annotated[str, Path(max_length=10)]):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, number FROM items WHERE id = %s",
                (item_id,)
            )
            row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Item not found")

    return row
```

Key detail:

```python
(item_id,)
```

The comma matters. In Python:

```python
(item_id)
```

is just `item_id` in parentheses. It is not a tuple.

## Route Conversion: GET All Items

The route has this response model:

```python
response_model=dict[str, Item]
```

That means FastAPI expects a response like:

```python
{
    "apple": {
        "name": "apple",
        "number": 1144
    }
}
```

Working route pattern:

```python
@app.get("/all", response_model=dict[str, Item])
async def get_all():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, number FROM items")
            rows = cur.fetchall()

    return {
        row["id"]: {
            "name": row["name"],
            "number": row["number"]
        }
        for row in rows
    }
```

Key detail:

```python
rows = cur.fetchall()
```

This calls the function and returns rows.

This is wrong:

```python
rows = cur.fetchall
```

That stores the function itself instead of calling it.

## Command-Line Testing

Start the FastAPI app:

```powershell
uvicorn main:app --reload
```

Health check:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/health/"
```

Create or update an item:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/postitem/apple?other=1144"
```

Get one item:

```powershell
Invoke-RestMethod -Method Get "http://127.0.0.1:8000/getitem/apple"
```

Because GET is the default, this also works:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/getitem/apple"
```

Get all items:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/all"
```

## Problems Debugged During the Session

### Password Authentication Failed

Error:

```text
FATAL: password authentication failed for user "percy"
```

The first suspicion was that the Docker Postgres volume had been initialized with old credentials. That can happen because Postgres only reads these values during first database initialization:

```yaml
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB
```

If the volume already exists, changing those values in `compose.yaml` does not rewrite the existing database user password.

The final cause was different: there was a local Windows `postgres` process already listening on `5432`, and Docker was also exposing `5432`.

The fix was to change Compose from:

```yaml
ports:
  - "5432:5432"
```

to:

```yaml
ports:
  - "5433:5432"
```

Then the app connection URL changed from:

```text
postgresql://percy:1144simplefast@localhost:5432/fastapi_app_db
```

to:

```text
postgresql://percy:1144simplefast@localhost:5433/fastapi_app_db
```

### Invalid SQL in INSERT

Wrong:

```python
cur.execute(
    """
    INSERT INTO items (id, name, number)
    VALUES %s %s %s
    """,
    (item_id, item_id, other)
)
```

Right:

```python
cur.execute(
    """
    INSERT INTO items (id, name, number)
    VALUES (%s, %s, %s)
    """,
    (item_id, item_id, other)
)
```

SQL needs parentheses and commas around values.

### Cursor Is Closed

Error:

```text
psycopg.InterfaceError: the cursor is closed
```

Cause:

```python
with conn.cursor() as cur:
    cur.execute(...)

row = cur.fetchone()
```

The cursor is closed when the `with conn.cursor()` block ends.

Fix:

```python
with conn.cursor() as cur:
    cur.execute(...)
    row = cur.fetchone()
```

Fetch while the cursor is still open.

### Returning `cur.fetchall` Instead of `cur.fetchall()`

Error:

```text
Input should be a valid dictionary
input: <bound method Cursor.fetchall ...>
```

Cause:

```python
data = cur.fetchall
```

Fix:

```python
data = cur.fetchall()
```

Without parentheses, Python gives you the function object instead of the function result.

### Response Model Shape

This response model:

```python
response_model=dict[str, Item]
```

expects:

```python
{
    "some_id": {
        "name": "some_id",
        "number": 1144
    }
}
```

It does not expect a plain list of database rows.

That is why `/all` transforms rows into a dictionary:

```python
return {
    row["id"]: {
        "name": row["name"],
        "number": row["number"]
    }
    for row in rows
}
```

## Key Concepts

### In-Memory Data vs Database Data

A Python dict:

```python
data = {}
```

lives only inside the current Python process. If the app restarts, the data is gone.

Postgres runs as a separate service. The FastAPI app connects to it and sends SQL commands. Data survives app restarts because it is stored by Postgres.

### Host Port vs Container Port

This Compose line:

```yaml
ports:
  - "5433:5432"
```

means:

```text
host port 5433 -> container port 5432
```

Your FastAPI app is running on Windows, outside the container, so it uses:

```text
localhost:5433
```

Postgres inside the container still listens on:

```text
5432
```

### Parameterized Queries

Use placeholders:

```python
cur.execute(
    "SELECT name, number FROM items WHERE id = %s",
    (item_id,)
)
```

Do not build SQL with f-strings:

```python
cur.execute(f"SELECT name, number FROM items WHERE id = '{item_id}'")
```

Parameterized queries let the database driver safely handle user input and protect against SQL injection.

### Context Managers

This pattern:

```python
with get_connection() as conn:
    with conn.cursor() as cur:
        ...
```

automatically opens and closes the connection and cursor.

Anything that needs the cursor must happen inside the cursor block.

### FastAPI Response Models

FastAPI validates your return value against the `response_model`.

If the route says:

```python
response_model=Item
```

then return something shaped like:

```python
{"name": "apple", "number": 1144}
```

If the route says:

```python
response_model=dict[str, Item]
```

then return something shaped like:

```python
{
    "apple": {"name": "apple", "number": 1144}
}
```

Response validation errors are useful because they tell you when your route is returning a different shape than promised.

## Strategies That Worked

Convert one route at a time:

1. Make `POST /postitem/{item_id}` insert into the database.
2. Make `GET /getitem/{item_id}` select one row.
3. Make `GET /all` select all rows.

When a request returns `Internal Server Error`, look at the `uvicorn` terminal. PowerShell usually only says `Internal Server Error`, but the actual Python or database exception is printed by `uvicorn`.

When debugging database connection problems, separate these questions:

1. Is the container running?
2. Is the expected port exposed?
3. Is another process already using that port?
4. Can `psql` connect?
5. Can Python connect with the same credentials?
6. Is the app using the same URL you tested?

## Ways to Improve the App

### Move Secrets Out of Source Code

Current learning version:

```python
DATABASE_URL = "postgresql://percy:1144simplefast@localhost:5433/fastapi_app_db"
```

Better later:

```python
DATABASE_URL = os.environ["DATABASE_URL"]
```

Then set it in PowerShell:

```powershell
$env:DATABASE_URL = "postgresql://percy:1144simplefast@localhost:5433/fastapi_app_db"
```

This keeps passwords out of the code.

### Use `def` for Sync Database Calls

The current app uses normal blocking `psycopg` calls inside `async def` routes. For learning, this is okay.

Later, either:

1. Use plain `def` routes with sync `psycopg`.
2. Use an async database client with `async def`.

Example direction:

```python
@app.get("/getitem/{item_id}", response_model=Item)
def get_item(...):
    ...
```

### Use More REST-Like Route Names

Current learning routes:

```text
POST /postitem/{item_id}
GET /getitem/{item_id}
GET /all
```

More common API style:

```text
POST /items/{item_id}
GET /items/{item_id}
GET /items
```

### Add Migrations Later

Right now, the table is created manually:

```sql
CREATE TABLE items (...);
```

Later, learn a migration tool like Alembic. Migrations track database schema changes over time.

### Learn SQLAlchemy or SQLModel Later

Direct SQL with `psycopg` is useful for learning what is actually happening.

After this feels comfortable, learn one of:

1. SQLAlchemy Core or ORM
2. SQLModel

These tools can reduce repetitive SQL for larger apps, but direct SQL is a good first step.

### Add Tests

Useful tests later:

1. `GET /health/` returns `{"status": "ok"}`.
2. `POST /postitem/apple?other=1144` returns the item.
3. `GET /getitem/apple` returns the same item.
4. `GET /getitem/missing` returns 404.
5. `GET /all` returns a dictionary of items.

### Add Startup Checks

Later, the app could check database connectivity on startup or provide a richer health endpoint.

For example, a simple health route only checks that FastAPI is alive:

```python
@app.get("/health/")
async def get_health():
    return {"status": "ok"}
```

A database health check would also verify that Postgres can be reached.

## Learning Checklist

You now have examples of:

1. Running Postgres locally with Docker Compose.
2. Mapping a container port to a different host port.
3. Connecting FastAPI to Postgres with `psycopg`.
4. Creating a table manually with SQL.
5. Using `INSERT ... ON CONFLICT`.
6. Using `SELECT ... WHERE id = %s`.
7. Fetching one row with `fetchone()`.
8. Fetching many rows with `fetchall()`.
9. Returning data that matches a FastAPI `response_model`.
10. Debugging common Postgres and FastAPI errors from tracebacks.

## Recommended Next Steps

1. Change the hardcoded database URL to `os.environ["DATABASE_URL"]`.
2. Rename routes to `/items` and `/items/{item_id}` once you understand the current version.
3. Add a `DELETE /items/{item_id}` route.
4. Add a `PUT /items/{item_id}` route.
5. Learn how to use Alembic for schema migrations.
6. Learn how to write basic FastAPI tests with `TestClient`.

