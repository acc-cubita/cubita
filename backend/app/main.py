from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import (
    accounts,
    auth,
    banking,
    billing,
    integration,
    inventory,
    invoices,
    journal,
    members,
    payroll,
    period_close,
    quotations,
    reports,
    returns,
    transfers,
    treasury,
)

settings = get_settings()

app = FastAPI(title="Cubita API", docs_url=None if settings.is_production else "/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(members.router)
app.include_router(accounts.router)
app.include_router(journal.router)
app.include_router(inventory.router)
app.include_router(invoices.router)
app.include_router(quotations.router)
app.include_router(returns.router)
app.include_router(transfers.router)
app.include_router(reports.router)
app.include_router(banking.router)
app.include_router(payroll.router)
app.include_router(period_close.router)
app.include_router(integration.router)
app.include_router(billing.router)
app.include_router(treasury.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
