import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.orders import router as orders_router
from app.api.plan import router as plan_router
from app.db.db import Base, SessionLocal, engine, get_db
from app.db.models.product import Product, Store
from app.db.schemas.product import ProductOut, StoreOut
from app.db.seed import seed
from app.errors import BusinessRuleError, NotFoundError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="Putka – plan produkcji", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174",
    ).split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(orders_router)
app.include_router(plan_router)


@app.exception_handler(NotFoundError)
def not_found_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(BusinessRuleError)
def business_rule_handler(_request: Request, exc: BusinessRuleError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(IntegrityError)
def integrity_error_handler(_request: Request, _exc: IntegrityError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": "Order could not be saved due to a data conflict"},
    )


@app.exception_handler(Exception)
def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/stores", response_model=list[StoreOut])
def list_stores(db: Session = Depends(get_db)):
    return db.scalars(select(Store).order_by(Store.name)).all()


@app.get("/products", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)):
    stmt = (
        select(Product)
        .where(Product.active.is_(True))
        .order_by(Product.category, Product.name)
    )
    return db.scalars(stmt).all()
