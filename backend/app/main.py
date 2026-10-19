import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine, get_db
from app.models import Product, Store
from app.schemas import ProductOut, StoreOut
from app.seed import seed


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
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


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
