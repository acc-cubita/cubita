"""قراردادِ خروجیِ بازار از سرورِ سازمانی.

هیچ مدلِ انبار یا حسابداری مستقیماً به ابر serialize نمی‌شود. افزودنِ هر فیلد
به این قرارداد باید آگاهانه باشد: فقط داده‌ای که خریدار برای معامله می‌بیند،
مقدارِ قابل‌عرضه، و رسیدِ بی‌جزئیاتِ ثبتِ محلی از مرزِ شرکت عبور می‌کنند.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.marketplace import (
    CatalogListingOut, CommissionPeriodOut, ConnectionOut, DistributorCardOut,
    OrderOut, ReturnOut, ZoneOut,
)


class MarketViewSnapshot(BaseModel):
    """Cloud-to-local market-only read cache, safe to show while offline."""

    model_config = ConfigDict(extra="forbid")

    captured_at: datetime
    distributors: list[DistributorCardOut]
    retailer_connections: list[ConnectionOut]
    distributor_connections: list[ConnectionOut]
    catalog: list[CatalogListingOut]
    retailer_orders: list[OrderOut]
    distributor_orders: list[OrderOut]
    retailer_returns: list[ReturnOut]
    distributor_returns: list[ReturnOut]
    zones: list[ZoneOut]
    commissions: list[CommissionPeriodOut]
    buyer_unread: int
    seller_unread: int


class MarketComponentSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_item_ref: UUID
    name: str = Field(max_length=300)
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=3)


class MarketListingSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_listing_ref: UUID
    kind: Literal["single", "pack"]
    title: str = Field(min_length=1, max_length=300)
    code: str = Field(max_length=60)
    unit: str = Field(max_length=20)
    wholesale_price: Decimal = Field(ge=0)
    consumer_price: Decimal = Field(ge=0)
    currency_code: str = Field(max_length=10)
    description: str = Field(max_length=10000)
    images: list[str] = Field(max_length=4)
    category: str = Field(max_length=100)
    is_published: bool
    extra_trades: list[str] = Field(max_length=100)
    bonus_threshold_qty: Decimal = Field(ge=0)
    bonus_qty: Decimal = Field(ge=0)
    min_order_qty: Decimal = Field(ge=0)
    max_order_qty: Decimal = Field(ge=0)
    daily_order_limit: int = Field(ge=0)
    available_qty: Decimal = Field(ge=0, max_digits=18, decimal_places=3)
    components: list[MarketComponentSnapshot] = Field(min_length=1, max_length=100)

    @field_validator("images")
    @classmethod
    def _images(cls, value: list[str]) -> list[str]:
        from app.schemas.marketplace import _validate_listing_images

        return _validate_listing_images(value)


class MarketCatalogPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation: UUID
    listings: list[MarketListingSnapshot] = Field(max_length=20)


class MarketSellerSettingsSnapshot(BaseModel):
    """Only public trade policy; no local accounting or gateway credentials."""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(max_length=200)
    is_active: bool
    require_delivery: bool
    return_policy: str = Field(max_length=2000)
    return_window_days: int = Field(ge=0, le=3650)
    target_trades: list[str] = Field(max_length=100)


class MarketCatalogFinalize(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation: UUID
    expected_count: int = Field(ge=0, le=10000)
    owner_approved: bool
    seller_settings: MarketSellerSettingsSnapshot


class MarketPostingReceipt(BaseModel):
    """ابر فقط می‌فهمد رویداد ثبت شده؛ شماره/جزئیاتِ سندِ محلی را نمی‌گیرد."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    order_id: UUID
    side: Literal["buyer", "seller"]
    outcome: Literal["posted", "retryable_error", "blocked"]
    error_code: str = Field(default="", max_length=60)


class MarketFinancialLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_item_ref: UUID
    name: str = Field(default="", max_length=300)
    unit: str = Field(default="", max_length=50)
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=0)
    discount: Decimal = Field(ge=0, max_digits=18, decimal_places=0)
    consumer_price: Decimal = Field(ge=0, max_digits=18, decimal_places=0)

    @model_validator(mode="after")
    def _amount(self):
        if self.discount > self.qty * self.unit_price:
            raise ValueError("تخفیف از مبلغ ردیف بیشتر است")
        return self


class MarketFinancialEvent(BaseModel):
    """Trade facts only; local contact, invoice and warehouse IDs are excluded."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    operation_ref: UUID
    order_id: UUID
    kind: Literal["order", "return"]
    return_id: UUID | None = None
    return_number: int | None = Field(default=None, ge=1)
    return_total: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=0)
    side: Literal["buyer", "seller"]
    counterparty_ref: UUID
    counterparty_name: str = Field(min_length=1, max_length=200)
    order_date: date
    order_number: int = Field(ge=1)
    cash_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=0)
    lines: list[MarketFinancialLine] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def _cash(self):
        if self.kind == "return" and (self.return_id is None or self.return_number is None or self.return_total is None or self.cash_amount != 0):
            raise ValueError("رویداد مرجوعی باید شناسه و شماره داشته باشد و تسویهٔ نقدی تازه نکند")
        if self.kind == "order" and (self.return_id is not None or self.return_number is not None or self.return_total is not None):
            raise ValueError("رویداد سفارش نباید شناسهٔ مرجوعی داشته باشد")
        total = sum((line.qty * line.unit_price - line.discount for line in self.lines), Decimal(0))
        if self.cash_amount > total:
            raise ValueError("سهم نقدی از جمع سفارش بیشتر است")
        return self


def listing_snapshot(
    listing: object, available_qty: Decimal, *, listing_ref: UUID, item_refs: dict[UUID, UUID]
) -> MarketListingSnapshot:
    """شناسه‌های بازار مستقل‌اند؛ حتی شناسهٔ کالای محلی به VPS نمی‌رود."""
    return MarketListingSnapshot(
        market_listing_ref=listing_ref,
        kind=listing.kind,
        title=listing.title,
        code=listing.code,
        unit=listing.unit,
        wholesale_price=Decimal(listing.wholesale_price),
        consumer_price=Decimal(listing.consumer_price),
        currency_code=listing.currency_code,
        description=listing.description,
        images=list(listing.images or []),
        category=listing.category,
        is_published=listing.is_published,
        extra_trades=list(listing.extra_trades or []),
        bonus_threshold_qty=Decimal(listing.bonus_threshold_qty),
        bonus_qty=Decimal(listing.bonus_qty),
        min_order_qty=Decimal(listing.min_order_qty),
        max_order_qty=Decimal(listing.max_order_qty),
        daily_order_limit=listing.daily_order_limit,
        available_qty=available_qty,
        components=[
            MarketComponentSnapshot(
                market_item_ref=item_refs[component.distributor_item_id],
                name=component.item_name,
                qty=Decimal(component.qty),
            )
            for component in listing.components
        ],
    )
