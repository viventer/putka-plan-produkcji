from fastapi import APIRouter

from app.api.deps import DbSession, Now
from app.db.schemas import OrderIn, OrderOut
from app.services.orders import create_order

router = APIRouter()


@router.post("/orders", response_model=OrderOut, status_code=201)
def post_order(payload: OrderIn, db: DbSession, now: Now) -> OrderOut:
    return OrderOut.model_validate(create_order(db, payload, now))
