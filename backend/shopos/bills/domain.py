from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import StrEnum

QUANTITY_SCALE = Decimal("0.001")
RATE_SCALE = Decimal("0.0001")
MONEY_SCALE = Decimal("0.01")
MAX_QUANTITY = Decimal("999999999.999")
MAX_RATE = Decimal("999999999999.9999")
MAX_MONEY = Decimal("999999999999.99")


class PriceBasis(StrEnum):
    RATE = "rate"
    AMOUNT = "amount"


@dataclass(frozen=True)
class CalculatedLine:
    quantity: Decimal
    unit_rate: Decimal
    line_amount: Decimal
    price_basis: PriceBasis


@dataclass(frozen=True)
class BillTotals:
    subtotal: Decimal
    tax_amount: Decimal
    charges_amount: Decimal
    total_amount: Decimal


@dataclass(frozen=True)
class BillLineDraft:
    quantity: Decimal | None = None
    unit_rate: Decimal | None = None
    line_amount: Decimal | None = None
    price_basis: PriceBasis | None = None

    def edit_quantity(self, value: Decimal | None) -> "BillLineDraft":
        quantity = checked_decimal(value, scale=QUANTITY_SCALE, maximum=MAX_QUANTITY, positive=True, field="quantity") if value is not None else None
        return replace(self, quantity=quantity)._recalculate()

    def edit_rate(self, value: Decimal | None) -> "BillLineDraft":
        rate = checked_decimal(value, scale=RATE_SCALE, maximum=MAX_RATE, positive=False, field="unit_rate") if value is not None else None
        return replace(self, unit_rate=rate, line_amount=None, price_basis=PriceBasis.RATE if rate is not None else None)._recalculate()

    def edit_amount(self, value: Decimal | None) -> "BillLineDraft":
        amount = checked_decimal(value, scale=MONEY_SCALE, maximum=MAX_MONEY, positive=False, field="line_amount") if value is not None else None
        return replace(self, line_amount=amount, unit_rate=None, price_basis=PriceBasis.AMOUNT if amount is not None else None)._recalculate()

    def _recalculate(self) -> "BillLineDraft":
        if self.quantity is None or self.price_basis is None:
            return replace(self, line_amount=None) if self.price_basis == PriceBasis.RATE else replace(self, unit_rate=None)
        if self.price_basis == PriceBasis.RATE:
            line = calculate_line(quantity=self.quantity, price_basis=self.price_basis, unit_rate=self.unit_rate)
        else:
            line = calculate_line(quantity=self.quantity, price_basis=self.price_basis, line_amount=self.line_amount)
        return replace(self, unit_rate=line.unit_rate, line_amount=line.line_amount)


def checked_decimal(value: Decimal, *, scale: Decimal, maximum: Decimal, positive: bool, field: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError(f"{field} must be a finite decimal")
    if (value <= 0 if positive else value < 0) or value > maximum:
        raise ValueError(f"{field} is outside the allowed range")
    try:
        if value != value.quantize(scale):
            raise ValueError(f"{field} has too many decimal places")
    except InvalidOperation as exc:
        raise ValueError(f"{field} is outside the allowed range") from exc
    return value.quantize(scale)


def calculate_line(
    *, quantity: Decimal, price_basis: PriceBasis, unit_rate: Decimal | None = None, line_amount: Decimal | None = None
) -> CalculatedLine:
    quantity = checked_decimal(quantity, scale=QUANTITY_SCALE, maximum=MAX_QUANTITY, positive=True, field="quantity")
    if price_basis == PriceBasis.RATE:
        if unit_rate is None or line_amount is not None:
            raise ValueError("rate basis requires only unit_rate")
        rate = checked_decimal(unit_rate, scale=RATE_SCALE, maximum=MAX_RATE, positive=False, field="unit_rate")
        raw_amount = quantity * rate
        if raw_amount > MAX_MONEY:
            raise ValueError("line_amount is outside the allowed range")
        amount = raw_amount.quantize(MONEY_SCALE, rounding=ROUND_HALF_UP)
        checked_decimal(amount, scale=MONEY_SCALE, maximum=MAX_MONEY, positive=False, field="line_amount")
    elif price_basis == PriceBasis.AMOUNT:
        if line_amount is None or unit_rate is not None:
            raise ValueError("amount basis requires only line_amount")
        amount = checked_decimal(line_amount, scale=MONEY_SCALE, maximum=MAX_MONEY, positive=False, field="line_amount")
        raw_rate = amount / quantity
        if raw_rate > MAX_RATE:
            raise ValueError("unit_rate is outside the allowed range")
        rate = raw_rate.quantize(RATE_SCALE, rounding=ROUND_HALF_UP)
        checked_decimal(rate, scale=RATE_SCALE, maximum=MAX_RATE, positive=False, field="unit_rate")
    else:
        raise ValueError("Unknown pricing basis")
    return CalculatedLine(quantity=quantity, unit_rate=rate, line_amount=amount, price_basis=price_basis)


def calculate_totals(lines: list[CalculatedLine], *, tax_amount: Decimal | None = None, charges_amount: Decimal | None = None) -> BillTotals:
    if not lines:
        raise ValueError("At least one line item is required")
    tax = checked_decimal(tax_amount if tax_amount is not None else Decimal("0"), scale=MONEY_SCALE, maximum=MAX_MONEY, positive=False, field="tax_amount")
    charges = checked_decimal(charges_amount if charges_amount is not None else Decimal("0"), scale=MONEY_SCALE, maximum=MAX_MONEY, positive=False, field="charges_amount")
    subtotal = sum((line.line_amount for line in lines), Decimal("0.00"))
    total = subtotal + tax + charges
    checked_decimal(subtotal, scale=MONEY_SCALE, maximum=MAX_MONEY, positive=False, field="subtotal")
    checked_decimal(total, scale=MONEY_SCALE, maximum=MAX_MONEY, positive=False, field="total_amount")
    return BillTotals(subtotal=subtotal, tax_amount=tax, charges_amount=charges, total_amount=total)
