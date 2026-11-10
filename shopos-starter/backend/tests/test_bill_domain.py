from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from shopos.bills.domain import BillLineDraft, PriceBasis, calculate_line, calculate_totals
from shopos.bills.schemas import BillCreateInput

D = Decimal


def test_rate_and_amount_edits_preserve_latest_pricing_basis():
    draft = BillLineDraft().edit_rate(D("12.3456"))
    assert draft.line_amount is None
    draft = draft.edit_quantity(D("2"))
    assert draft.line_amount == D("24.69")
    draft = draft.edit_quantity(D("3"))
    assert draft.unit_rate == D("12.3456")
    assert draft.line_amount == D("37.04")

    draft = draft.edit_amount(D("100.00"))
    assert draft.price_basis == PriceBasis.AMOUNT
    assert draft.unit_rate == D("33.3333")
    draft = draft.edit_quantity(D("6"))
    assert draft.line_amount == D("100.00")
    assert draft.unit_rate == D("16.6667")
    draft = draft.edit_rate(D("8.50"))
    assert draft.price_basis == PriceBasis.RATE
    assert draft.line_amount == D("51.00")


def test_amount_first_and_quantity_clearing_keep_entered_amount():
    draft = BillLineDraft().edit_amount(D("0.01"))
    assert draft.unit_rate is None
    draft = draft.edit_quantity(D("999999999.999"))
    assert draft.line_amount == D("0.01")
    assert draft.unit_rate == D("0.0000")
    draft = draft.edit_quantity(None)
    assert draft.line_amount == D("0.01")
    assert draft.unit_rate is None


def test_half_up_rounding_and_optional_totals():
    tiny = calculate_line(quantity=D("1"), price_basis=PriceBasis.RATE, unit_rate=D("0.005"))
    assert tiny.line_amount == D("0.01")
    second = calculate_line(quantity=D("3"), price_basis=PriceBasis.AMOUNT, line_amount=D("100.00"))
    assert second.unit_rate == D("33.3333")
    without_extras = calculate_totals([tiny, second])
    assert without_extras.subtotal == D("100.01")
    assert without_extras.tax_amount == D("0.00")
    assert without_extras.total_amount == D("100.01")
    with_extras = calculate_totals([tiny, second], tax_amount=D("5.50"), charges_amount=D("1.25"))
    assert with_extras.total_amount == D("106.76")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"quantity": D("0"), "price_basis": PriceBasis.RATE, "unit_rate": D("10")},
        {"quantity": D("-1"), "price_basis": PriceBasis.RATE, "unit_rate": D("10")},
        {"quantity": D("1.0001"), "price_basis": PriceBasis.RATE, "unit_rate": D("10")},
        {"quantity": D("1"), "price_basis": PriceBasis.RATE, "unit_rate": D("-0.01")},
        {"quantity": D("1"), "price_basis": PriceBasis.AMOUNT, "line_amount": D("1.001")},
        {"quantity": D("1"), "price_basis": PriceBasis.RATE, "unit_rate": D("1"), "line_amount": D("1")},
        {"quantity": D("1"), "price_basis": PriceBasis.AMOUNT},
        {"quantity": D("NaN"), "price_basis": PriceBasis.RATE, "unit_rate": D("1")},
        {"quantity": D("999999999.999"), "price_basis": PriceBasis.RATE, "unit_rate": D("999999999999.9999")},
    ],
)
def test_invalid_lines_are_rejected(kwargs):
    with pytest.raises(ValueError):
        calculate_line(**kwargs)


def valid_bill():
    return {
        "vendor_id": str(uuid4()),
        "bill_date": "2026-11-04",
        "proof_attachment_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "items": [
            {"item_id": str(uuid4()), "quantity": "2.000", "price_basis": "rate", "unit_rate": "12.3456"},
            {"item_id": str(uuid4()), "quantity": "3", "price_basis": "amount", "line_amount": "100.00"},
        ],
        "tax_amount": "5.50",
        "charges_amount": "1.25",
    }


def test_server_bill_schema_calculates_multiple_lines():
    bill = BillCreateInput.model_validate(valid_bill())
    assert bill.calculate_totals().subtotal == D("124.69")
    assert bill.calculate_totals().total_amount == D("131.44")


@pytest.mark.parametrize("field", ["vendor_id", "bill_date", "proof_attachment_id", "idempotency_key", "items"])
def test_required_bill_fields(field):
    payload = valid_bill()
    payload.pop(field)
    with pytest.raises(ValidationError):
        BillCreateInput.model_validate(payload)


def test_invalid_optional_money_and_binary_float_are_rejected():
    payload = valid_bill()
    payload["tax_amount"] = "-0.01"
    with pytest.raises(ValidationError):
        BillCreateInput.model_validate(payload)
    payload = valid_bill()
    payload["items"][0]["quantity"] = 0.1
    with pytest.raises(ValidationError, match="strings"):
        BillCreateInput.model_validate(payload)
    payload = valid_bill()
    payload["items"] = []
    with pytest.raises(ValidationError):
        BillCreateInput.model_validate(payload)
