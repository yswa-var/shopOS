package com.shopos.bills.form

/** Input control expected by the shared bill-form renderer. */
enum class BillInputKind {
    TEXT,
    DECIMAL,
    MONEY,
    DATE,
    PHOTO,
}

/**
 * UI metadata for one bill field.
 *
 * `key` is the stable API/domain name. `required` is a UI hint only: the backend
 * must enforce the same rule. Keep this registry as the obvious edit point for
 * bill form labels, field types, and required/optional changes.
 */
data class BillFieldSpec(
    val key: String,
    val label: String,
    val kind: BillInputKind,
    val required: Boolean,
    val visible: Boolean = true,
    val help: String? = null,
)

/**
 * Central field list for the bill form. Add a field here, then follow
 * docs/field-config.md to wire it through state, API, database, and detail view.
 */
object BillFormFields {
    val header: List<BillFieldSpec> = listOf(
        BillFieldSpec("vendor_id", "Vendor", BillInputKind.TEXT, required = true, visible = true),
        BillFieldSpec("bill_date", "Bill date", BillInputKind.DATE, required = true, visible = true),
        BillFieldSpec("tax_amount", "Tax (₹)", BillInputKind.MONEY, required = false, visible = true),
        BillFieldSpec("charges_amount", "Extra charges (₹)", BillInputKind.MONEY, required = false, visible = true),
        BillFieldSpec("proof_photo", "Proof photo", BillInputKind.PHOTO, required = true, visible = true),
    )

    val lineItem: List<BillFieldSpec> = listOf(
        BillFieldSpec("item_id", "Item", BillInputKind.TEXT, required = true, visible = true),
        BillFieldSpec("quantity", "Quantity", BillInputKind.DECIMAL, required = true, visible = true),
        // Either rate or amount is entered; the latest edit becomes the calculation basis.
        BillFieldSpec("unit_rate", "Unit rate (₹)", BillInputKind.MONEY, required = false, visible = true),
        BillFieldSpec("line_amount", "Amount (₹)", BillInputKind.MONEY, required = false, visible = true),
    )
}
