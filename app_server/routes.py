from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from db import Database
from repositories import (
    BillRepository,
    CatalogRepository,
    RecordNotFoundError,
    RequestConflictError,
)
from schemas import (
    BillCreate,
    BillDetail,
    BillResponse,
    ItemCreate,
    ItemResponse,
    VendorCreate,
    VendorResponse,
)


router = APIRouter()


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_catalog(database: Database = Depends(get_database)) -> CatalogRepository:
    return CatalogRepository(database)


def get_bills(database: Database = Depends(get_database)) -> BillRepository:
    return BillRepository(database)


@router.get("/")
async def root() -> dict[str, str]:
    return {"name": "ShopOS Bill Creator API", "version": "0.1.0"}


@router.get("/health")
async def health(database: Database = Depends(get_database)) -> JSONResponse:
    try:
        await database.fetch_one("SELECT 1 AS ok")
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable"},
        )
    return JSONResponse(content={"status": "ok"})


@router.get("/vendors", response_model=list[VendorResponse])
async def list_vendors(
    catalog: CatalogRepository = Depends(get_catalog),
) -> list[dict[str, Any]]:
    return await catalog.list_vendors()


@router.post(
    "/vendors", response_model=VendorResponse, status_code=status.HTTP_201_CREATED
)
async def create_vendor(
    payload: VendorCreate,
    catalog: CatalogRepository = Depends(get_catalog),
) -> dict[str, Any]:
    return await catalog.create_vendor(payload)


@router.get("/items", response_model=list[ItemResponse])
async def list_items(
    catalog: CatalogRepository = Depends(get_catalog),
) -> list[dict[str, Any]]:
    return await catalog.list_items()


@router.post(
    "/items", response_model=ItemResponse, status_code=status.HTTP_201_CREATED
)
async def create_item(
    payload: ItemCreate,
    catalog: CatalogRepository = Depends(get_catalog),
) -> dict[str, Any]:
    return await catalog.create_item(payload)


@router.post(
    "/bills", response_model=BillResponse, status_code=status.HTTP_201_CREATED
)
async def create_bill(
    payload: BillCreate,
    bills: BillRepository = Depends(get_bills),
) -> dict[str, Any]:
    try:
        return await bills.create(payload)
    except RecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RequestConflictError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/bills/{bill_id}", response_model=BillDetail)
async def get_bill(
    bill_id: int,
    bills: BillRepository = Depends(get_bills),
) -> dict[str, Any]:
    try:
        return await bills.get(bill_id)
    except RecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
