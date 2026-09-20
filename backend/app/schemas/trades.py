"""شکلِ فهرستِ اصناف روی سیم."""
from pydantic import BaseModel


class TradeOut(BaseModel):
    key: str
    label: str


class TradeGroupOut(BaseModel):
    key: str
    label: str
    trades: list[TradeOut]
