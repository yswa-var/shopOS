package com.shopos.bills.form

import com.shopos.bills.domain.BillMath
import com.shopos.bills.domain.PriceBasis
import java.io.File
import java.math.BigDecimal
import java.time.LocalDate
import java.util.UUID

data class BillLineSnapshot(
    val localId: String = UUID.randomUUID().toString(),
    val itemId: String = "",
    val itemName: String = "",
    val quantity: String = "1",
    val unitRate: String = "",
    val lineAmount: String = "",
    val priceBasis: String = "rate",
) {
    fun calculated() = BillMath.line(
        BigDecimal(quantity),
        if (priceBasis == "amount") PriceBasis.AMOUNT else PriceBasis.RATE,
        unitRate = if (priceBasis == "rate") BigDecimal(unitRate) else null,
        lineAmount = if (priceBasis == "amount") BigDecimal(lineAmount) else null,
    )

    fun withQuantity(value: String) = copy(quantity = value).derive()
    fun withRate(value: String) = copy(unitRate = value, priceBasis = "rate").derive()
    fun withAmount(value: String) = copy(lineAmount = value, priceBasis = "amount").derive()

    private fun derive(): BillLineSnapshot = try {
        val result = calculated()
        copy(unitRate = result.unitRate.stripTrailingZeros().toPlainString(), lineAmount = result.lineAmount.toPlainString())
    } catch (_: Exception) {
        if (priceBasis == "rate") copy(lineAmount = "") else copy(unitRate = "")
    }
}

data class BillLineRequest(
    val item_id: String,
    val quantity: String,
    val price_basis: String,
    val unit_rate: String? = null,
    val line_amount: String? = null,
)

data class BillCreateRequest(
    val vendor_id: String,
    val bill_date: String,
    val proof_attachment_id: String,
    val idempotency_key: String,
    val items: List<BillLineRequest>,
    val tax_amount: String,
    val charges_amount: String,
)

data class BillDraftSnapshot(
    val schemaVersion: Int = 1,
    val idempotencyKey: String = UUID.randomUUID().toString(),
    val vendorId: String = "",
    val vendorName: String = "",
    val billDate: String = LocalDate.now().toString(),
    val lines: List<BillLineSnapshot> = listOf(BillLineSnapshot()),
    val taxAmount: String = "",
    val chargesAmount: String = "",
    val proofPath: String? = null,
    val proofUploadId: String = UUID.randomUUID().toString(),
    val proofAttachmentId: String? = null,
    val submitted: Boolean = false,
) {
    fun totalText(): String = try {
        BillMath.totals(lines.map { it.calculated() }, optionalMoney(taxAmount), optionalMoney(chargesAmount)).totalAmount.toPlainString()
    } catch (_: Exception) { "—" }

    fun request(proofId: String): BillCreateRequest {
        require(vendorId.isNotBlank()) { "Choose a vendor" }
        LocalDate.parse(billDate)
        require(lines.isNotEmpty()) { "Add an item" }
        require(proofPath != null && File(proofPath).isFile) { "Take a proof photo" }
        require(File(proofPath).length() in 1..15_000_000) { "Photo must be under 15 MB" }
        val calculated = lines.map { line ->
            require(line.itemId.isNotBlank()) { "Choose an item" }
            line.calculated()
        }
        BillMath.totals(calculated, optionalMoney(taxAmount), optionalMoney(chargesAmount))
        return BillCreateRequest(
            vendorId, billDate, proofId, idempotencyKey,
            lines.mapIndexed { index, line ->
                val result = calculated[index]
                BillLineRequest(line.itemId, result.quantity.toPlainString(), line.priceBasis,
                    unit_rate = if (line.priceBasis == "rate") result.unitRate.toPlainString() else null,
                    line_amount = if (line.priceBasis == "amount") result.lineAmount.toPlainString() else null)
            },
            optionalMoney(taxAmount)?.toPlainString() ?: "0.00",
            optionalMoney(chargesAmount)?.toPlainString() ?: "0.00",
        )
    }
}

private fun optionalMoney(text: String): BigDecimal? = text.takeIf { it.isNotBlank() }?.let(::BigDecimal)
