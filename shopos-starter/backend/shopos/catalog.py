from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from shopos.audit import record_event
from shopos.auth import CurrentUser, Db, require_permission
from shopos.models import CatalogTerm, Item, User, Vendor

router = APIRouter(prefix="/catalog", tags=["catalog"])
CanRead = Annotated[User, Depends(require_permission("catalog:read"))]
CanWrite = Annotated[User, Depends(require_permission("catalog:write"))]


class CatalogCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    aliases: list[str] = Field(default_factory=list, max_length=8)


class AliasCreate(BaseModel):
    alias: str = Field(min_length=1, max_length=100)


class CatalogResponse(BaseModel):
    id: UUID
    name: str
    aliases: list[str]


def clean_name(value: str) -> tuple[str, str]:
    display = " ".join(value.split())
    normalized = display.casefold()
    if not display or len(display) > 100 or len(normalized) > 100:
        raise HTTPException(status_code=422, detail="Name must contain 1–100 characters")
    return display, normalized


def response_for(entity: Vendor | Item) -> CatalogResponse:
    return CatalogResponse(
        id=entity.id,
        name=entity.name,
        aliases=sorted((term.display_term for term in entity.terms if term.normalized_term != entity.normalized_name), key=str.casefold),
    )


def conflict(db: Session, *, kind: str, normalized: str) -> None:
    existing = db.scalar(select(CatalogTerm).where(CatalogTerm.kind == kind, CatalogTerm.normalized_term == normalized))
    if existing is not None:
        raise HTTPException(status_code=409, detail={"message": "Name or alias already exists", "existing_id": str(existing.vendor_id or existing.item_id)})


def create_entry(db: Session, *, model: type[Vendor] | type[Item], kind: str, payload: CatalogCreate, actor_id: UUID) -> CatalogResponse:
    name, normalized = clean_name(payload.name)
    terms = [(name, normalized)] + [clean_name(alias) for alias in payload.aliases]
    keys = [key for _, key in terms]
    if len(set(keys)) != len(keys):
        raise HTTPException(status_code=422, detail="Name and aliases must be distinct")
    entity = model(name=name, normalized_name=normalized, created_by=actor_id)
    db.add(entity)
    try:
        db.flush()
        for display, key in terms:
            db.add(CatalogTerm(kind=kind, display_term=display, normalized_term=key, vendor_id=entity.id if kind == "vendor" else None, item_id=entity.id if kind == "item" else None))
        record_event(db, actor_id=actor_id, action=f"catalog.{kind}.create", target_type=kind, target_id=entity.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        for _, key in terms:
            conflict(db, kind=kind, normalized=key)
        raise
    db.refresh(entity)
    return response_for(entity)


def add_alias(db: Session, *, model: type[Vendor] | type[Item], kind: str, entity_id: UUID, alias: str, actor_id: UUID) -> CatalogResponse:
    entity = db.get(model, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Catalog entry not found")
    display, normalized = clean_name(alias)
    db.add(CatalogTerm(kind=kind, display_term=display, normalized_term=normalized, vendor_id=entity.id if kind == "vendor" else None, item_id=entity.id if kind == "item" else None))
    record_event(db, actor_id=actor_id, action=f"catalog.{kind}.alias.create", target_type=kind, target_id=entity.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        conflict(db, kind=kind, normalized=normalized)
        raise
    db.refresh(entity)
    return response_for(entity)


def search_entries(db: Session, *, model: type[Vendor] | type[Item], kind: str, query: str) -> list[CatalogResponse]:
    normalized = " ".join(query.split()).casefold()
    statement = select(model).options(selectinload(model.terms))
    if normalized:
        target = CatalogTerm.vendor_id if kind == "vendor" else CatalogTerm.item_id
        matching = exists(select(CatalogTerm.id).where(target == model.id, CatalogTerm.kind == kind, CatalogTerm.normalized_term.contains(normalized, autoescape=True)))
        exact = exists(select(CatalogTerm.id).where(target == model.id, CatalogTerm.kind == kind, CatalogTerm.normalized_term == normalized))
        prefix = exists(select(CatalogTerm.id).where(target == model.id, CatalogTerm.kind == kind, CatalogTerm.normalized_term.startswith(normalized, autoescape=True)))
        statement = statement.where(matching).order_by(case((exact, 0), (prefix, 1), else_=2))
    statement = statement.order_by(model.use_count.desc(), model.last_used_at.desc().nulls_last(), model.created_at.desc(), model.name).limit(20)
    return [response_for(entity) for entity in db.scalars(statement).all()]


@router.get("/vendors", response_model=list[CatalogResponse])
def search_vendors(db: Db, _access: CanRead, q: str = Query(default="", max_length=100)) -> list[CatalogResponse]:
    return search_entries(db, model=Vendor, kind="vendor", query=q)


@router.post("/vendors", status_code=201, response_model=CatalogResponse)
def create_vendor(payload: CatalogCreate, db: Db, user: CurrentUser, _access: CanWrite) -> CatalogResponse:
    return create_entry(db, model=Vendor, kind="vendor", payload=payload, actor_id=user.id)


@router.post("/vendors/{entity_id}/aliases", status_code=201, response_model=CatalogResponse)
def add_vendor_alias(entity_id: UUID, payload: AliasCreate, db: Db, user: CurrentUser, _access: CanWrite) -> CatalogResponse:
    return add_alias(db, model=Vendor, kind="vendor", entity_id=entity_id, alias=payload.alias, actor_id=user.id)


@router.get("/items", response_model=list[CatalogResponse])
def search_items(db: Db, _access: CanRead, q: str = Query(default="", max_length=100)) -> list[CatalogResponse]:
    return search_entries(db, model=Item, kind="item", query=q)


@router.post("/items", status_code=201, response_model=CatalogResponse)
def create_item(payload: CatalogCreate, db: Db, user: CurrentUser, _access: CanWrite) -> CatalogResponse:
    return create_entry(db, model=Item, kind="item", payload=payload, actor_id=user.id)


@router.post("/items/{entity_id}/aliases", status_code=201, response_model=CatalogResponse)
def add_item_alias(entity_id: UUID, payload: AliasCreate, db: Db, user: CurrentUser, _access: CanWrite) -> CatalogResponse:
    return add_alias(db, model=Item, kind="item", entity_id=entity_id, alias=payload.alias, actor_id=user.id)
