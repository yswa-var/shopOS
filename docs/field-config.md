# Changing bill form fields

## One obvious place to start

Bill form metadata lives in:

`android/app/src/main/java/com/shopos/bills/form/BillFormFields.kt`

Each field describes its API key, visible label, input type, required status, and visibility. The screen should render this registry through shared input components instead of declaring field labels and rules in several screens.

Example pattern (Q00/Q03 should turn this into compiling app code):

```kotlin
enum class BillInputKind { TEXT, DECIMAL, MONEY, DATE, PHOTO }

data class BillFieldSpec(
    val key: String,                 // Stable API/domain key. Do not rename casually.
    val label: String,               // Text shown to employees.
    val kind: BillInputKind,
    val required: Boolean,           // UI hint; backend enforces the same rule.
    val visible: Boolean = true,
    val help: String? = null,
)

object BillFormFields {
    // Add or change bill-entry fields here first, then follow the checklist below.
    val header = listOf(
        BillFieldSpec("vendor_id", "Vendor", BillInputKind.TEXT, required = true),
        BillFieldSpec("bill_date", "Bill date", BillInputKind.DATE, required = true),
        BillFieldSpec("tax_amount", "Tax (₹)", BillInputKind.MONEY, required = false),
        BillFieldSpec("charges_amount", "Extra charges (₹)", BillInputKind.MONEY, required = false),
        BillFieldSpec("proof_photo", "Proof photo", BillInputKind.PHOTO, required = true),
    )

    val lineItem = listOf(
        BillFieldSpec("item_id", "Item", BillInputKind.TEXT, required = true),
        BillFieldSpec("quantity", "Quantity", BillInputKind.DECIMAL, required = true),
        BillFieldSpec("unit_rate", "Rate per kg (₹)", BillInputKind.MONEY, required = false),
        BillFieldSpec("line_amount", "Amount (₹)", BillInputKind.MONEY, required = false),
    )
}
```

This is a pattern for Codex to implement, not a compiled app yet. Q00 creates the Android project and package structure.

## Change checklist

1. Update the field registry and provide a short comment for any non-obvious rule.
2. Add the value to the form state and request/response model.
3. Add UI formatting and validation. Required fields should show a clear marker and error.
4. Update the FastAPI request/response schema. Backend validation is authoritative.
5. If persisted, add an Alembic migration and choose a safe default or nullable transition.
6. Update bill creation, query/detail display, and any export/report mapping that includes the field.
7. Add focused tests for valid, missing, invalid, and legacy-record behavior.
8. Update PRD/WORKLOG and commit only after checks pass.

## Required to optional / optional to required

- **Required → optional:** make UI optional; accept `null`/missing in API; remove or relax the database `NOT NULL` constraint in a migration; define how old records display; test omission.
- **Optional → required:** decide how existing rows will be backfilled; migrate only after a safe default/data plan; enforce in API and UI; test missing input and old records.
- Never change only the Compose marker. A field is truly required only when server-side validation enforces it.

## Calculation fields

Quantity, rate, and amount are linked values. Keep the latest edited pricing basis in form state. Use `BigDecimal` (or integer paise with explicit unit conversions), define rounding once, and repeat validation on the server. Do not store a recalculated number as if it was directly entered without retaining the source inputs.
