"""Per-user shopping basket API."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.helpers import require_user
from app.core.warmup import wait_until_db_ready
from app.database import get_db
from app.models import User, UserCartItem
from app.schemas import CartItemOut, CartOut, CartReplaceIn

router = APIRouter(
    prefix="/api/v1/cart",
    tags=["cart"],
    dependencies=[Depends(wait_until_db_ready)],
)


def _cart_out(rows: list[UserCartItem]) -> CartOut:
    updated_at: float | None = None
    for r in rows:
        if r.updated_at is None:
            continue
        ts = r.updated_at.timestamp()
        if updated_at is None or ts > updated_at:
            updated_at = ts
    return CartOut(
        items=[CartItemOut(product_name=r.product_name, quantity=r.quantity) for r in rows],
        updated_at=updated_at,
    )


@router.get("", response_model=CartOut)
async def get_cart(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserCartItem)
        .where(UserCartItem.user_id == user.id)
        .order_by(UserCartItem.product_name.asc())
    )
    return _cart_out(list(result.scalars().all()))


@router.put("", response_model=CartOut)
async def replace_cart(
    body: CartReplaceIn,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Replace the signed-in user's basket with the provided items."""
    # Collapse duplicate names from the client (keep last / sum)
    merged: dict[str, int] = {}
    for item in body.items:
        name = item.product_name.strip()
        if not name:
            continue
        merged[name] = min(999, merged.get(name, 0) + int(item.quantity))

    await db.execute(delete(UserCartItem).where(UserCartItem.user_id == user.id))

    now = datetime.now(timezone.utc)
    rows = [
        UserCartItem(
            user_id=user.id,
            product_name=name,
            quantity=qty,
            updated_at=now,
        )
        for name, qty in sorted(merged.items())
        if qty > 0
    ]
    db.add_all(rows)
    await db.flush()
    return _cart_out(rows)
