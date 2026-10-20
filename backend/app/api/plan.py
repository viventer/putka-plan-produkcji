import re
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BeforeValidator

from app.api.deps import DbSession
from app.db.schemas.plan import ProductionPlanOut
from app.services.plan import build_plan

router = APIRouter()

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _parse_iso_date(value: str) -> date:
    # Query values arrive as strings. Pydantic's date otherwise accepts a datetime.
    if not isinstance(value, str) or _ISO_DATE.fullmatch(value) is None:
        raise ValueError("Date must be YYYY-MM-DD")
    return date.fromisoformat(value)


@router.get("/production-plan", response_model=ProductionPlanOut)
def get_production_plan(
    day: Annotated[date, BeforeValidator(_parse_iso_date), Query(alias="date")],
    db: DbSession,
) -> ProductionPlanOut:
    return build_plan(db, day)
