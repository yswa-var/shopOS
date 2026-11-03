# Bill calculation and validation contract

Q03 defines the bill model and arithmetic used by Q05. A saved bill has one vendor, a bill date, one or more item lines, a proof attachment ID, a creator, an idempotency key, timestamps, optional tax and charges, and a final payable total. The proof attachment ID is required in the input and database. Q04 provides its attachment table and foreign key; Q05 implements saving.

## Decimal policy

| Value | Precision | Allowed range |
|---|---:|---:|
| Quantity | 3 decimal places | More than 0, at most 999999999.999 |
| Unit rate | 4 decimal places | 0 to 999999999999.9999 |
| Money (line amount, tax, charges, totals) | 2 decimal places | 0 to 999999999999.99 |

Derived values use `ROUND_HALF_UP`. A rate-entered line calculates `line_amount = round(quantity × unit_rate, 2)`. An amount-entered line keeps its exact entered amount and displays `unit_rate = round(line_amount ÷ quantity, 4)`. Changing quantity preserves whichever price was last entered. Editing the other price changes the basis. Rounding the derived rate back into an amount is not authoritative for an amount-entered line.

`subtotal` is the sum of rounded line amounts. `total_amount = subtotal + tax_amount + charges_amount`; omitted tax or charges mean zero. Negative money, non-positive quantity, excess decimal places, non-finite values, and totals beyond the database precision are rejected. Zero-valued lines remain valid for no-charge purchases. The request sends decimal values as strings, never JSON floating-point numbers.

## Creation schema for Q05

`BillCreateInput` requires `vendor_id`, `bill_date`, `proof_attachment_id`, `idempotency_key`, and a nonempty `items` array. Each line requires `item_id`, `quantity`, and `price_basis` (`rate` or `amount`). A rate-based line sends only `unit_rate`; an amount-based line sends only `line_amount`. The backend computes the other price and all totals. Android uses `BigDecimal`; the backend uses `Decimal`. Store the basis with each line so a later correction retains the employee's original pricing choice.

The bill tables already reserve a unique `(created_by, idempotency_key)` pair to prevent duplicate saves. Q05 must enforce this in its transaction and return the same bill for a retry.
