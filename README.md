# FastAPI Production

A production-ready async FastAPI application with PostgreSQL for product management.

## Tech Stack

- **FastAPI** — async web framework
- **SQLAlchemy** — async ORM with `asyncpg` driver
- **PostgreSQL 15** — database
- **Gunicorn + Uvicorn** — production ASGI server
- **Pydantic** — request/response validation
- **uv** — package manager

## Prerequisites

- Python 3.12+
- PostgreSQL (or Docker)
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
# Install dependencies
uv sync

# Set database URL (optional, defaults to local)
export DATABASE_URL="postgresql+asyncpg://myuser:mypassword@localhost:5432/mydb"
```

## Running

```bash
# Development (with hot reload)
uv run uvicorn main:app --reload

# Production (multi-worker)
uv run gunicorn main:app -c gunicorn.conf.py
```

## API Endpoints

### `GET /products`

List products with pagination and search.

| Parameter   | Type   | Default | Description          |
|-------------|--------|---------|----------------------|
| `page`      | int    | 1       | Page number          |
| `page_size` | int    | 20      | Items per page (1-100) |
| `search`    | string | —       | Search by product name |

### `POST /products`

Create a new product.

```json
{
  "name": "Widget",
  "price": 9.99,
  "description": "Optional description"
}
```

## Project Structure

```
├── main.py              # App setup and API endpoints
├── database.py          # Async engine, session, and DB dependency
├── models.py            # SQLAlchemy ORM models
├── schemas.py           # Pydantic request/response schemas
├── gunicorn.conf.py     # Production server config
└── pyproject.toml       # Dependencies
```

## API Docs

Interactive docs available at `http://localhost:8000/docs` when the server is running.
