import logging
import math
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from cache import get_cache, invalidate_cache, redis, set_cache
from database import engine, get_db
from models import Base, Product
from schemas import PaginatedResponse, ProductCreate, ProductResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Products API", version="1.0.0", lifespan=lifespan)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    status = {"app": "healthy", "postgres": "healthy", "redis": "healthy"}
    healthy = True

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        status["postgres"] = "unhealthy"
        healthy = False

    try:
        await redis.ping()
    except Exception:
        status["redis"] = "unhealthy"
        healthy = False

    if not healthy:
        return JSONResponse(status_code=503, content=status)
    return status


@app.get("/products", response_model=PaginatedResponse)
async def list_products(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by product name"),
    db: AsyncSession = Depends(get_db),
):
    # Check cache
    cached = await get_cache("products", page=page, page_size=page_size, search=search)
    if cached:
        return cached

    try:
        query = select(Product)

        if search:
            query = query.filter(Product.name.ilike(f"%{search}%"))

        count_query = select(func.count()).select_from(query.subquery())
        result = await db.execute(count_query)
        total = result.scalar()

        query = (
            query.order_by(Product.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(query)
        products = result.scalars().all()
    except OperationalError:
        logger.exception("Database connection error during list_products")
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")

    response = PaginatedResponse(
        items=products,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )

    # Cache the response
    await set_cache(response.model_dump(), "products", page=page, page_size=page_size, search=search)

    return response


@app.post("/products", response_model=ProductResponse, status_code=201)
async def add_product(product: ProductCreate, db: AsyncSession = Depends(get_db)):
    db_product = Product(**product.model_dump())
    try:
        db.add(db_product)
        await db.commit()
        await db.refresh(db_product)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Product already exists")
    except OperationalError:
        await db.rollback()
        logger.exception("Database connection error during add_product")
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except SQLAlchemyError:
        await db.rollback()
        logger.exception("Failed to create product")
        raise HTTPException(status_code=500, detail="Failed to create product")

    # Invalidate product list cache after new product is added
    await invalidate_cache("products")

    return db_product
