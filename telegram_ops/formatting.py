"""Telegram response formatting."""

from __future__ import annotations

from collections.abc import Sequence

from db_ops.item_repository import ItemMatch


def _money(value: float | None) -> str:
    return "—" if value is None else f"₹{value:,.2f}"


def _price(value: float | None, unit: str | None) -> str:
    return "—" if value is None else f"{_money(value)} / {unit or 'unit'}"


def format_results(query: str, matches: Sequence[ItemMatch]) -> str:
    if not matches:
        return f'No matching items found for "{query}".\nTry a shorter name or a different spelling.'

    lines = [f'Price matches for "{query}" ({len(matches)}):']
    for match in matches:
        lines.extend(
            [
                "",
                f"{match.item_id}. {match.item_name}",
                f"Dar: {_price(match.purchase_unit_price, match.purchase_unit)}",
                f"Lowest dar: {_price(match.lowest_purchase_price, match.lowest_price_unit)}",
                f"Sell: {_price(match.sell_price, match.sell_unit)}",
                f"{match.supplier or 'Supplier unknown'} || {match.date_purchased or 'Purchase date unknown'}",
            ]
        )
    return "\n".join(lines)
