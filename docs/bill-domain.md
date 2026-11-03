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

## Creation schema and save flow

`BillCreateInput` requires `vendor_id`, `bill_date`, `proof_attachment_id`, `idempotency_key`, and a nonempty `items` array. Each line requires `item_id`, `quantity`, and `price_basis` (`rate` or `amount`). A rate-based line sends only `unit_rate`; an amount-based line sends only `line_amount`. The backend computes the other price and all totals. Android uses `BigDecimal`; the backend uses `Decimal`. Store the basis with each line so a later correction retains the employee's original pricing choice.

`POST /bills` requires `bills:create`. It validates the vendor and items, then locks the ready proof and checks that the creator uploaded it. A proof can belong to one bill only. The transaction writes the bill, ordered lines, catalog usage, and one audit event. A retry with the same creator, key, and payload returns the existing bill; a changed payload using that key returns 409. The nullable request fingerprint column is an additive migration for older development databases.

The Android form stores one Room draft per employee, including raw field text, selected IDs, a private photo path, stable upload ID, and stable bill idempotency key. It uploads the CameraX JPEG through a short-lived signed URL, completes the proof, then sends the bill. Once the bill request is sent, the draft is frozen so a timeout can be retried with the same payload. A successful response deletes the draft and its local photo. The debug APK allows cleartext traffic for local emulator endpoints; release builds require HTTPS. Q06 adds query/detail screens for saved bills.
