package com.shopos.bills.domain

import java.math.BigDecimal
import java.math.RoundingMode

enum class PriceBasis(val wireValue: String) { RATE("rate"), AMOUNT("amount") }

data class CalculatedLine(
    val quantity: BigDecimal,
    val unitRate: BigDecimal,
    val lineAmount: BigDecimal,
    val priceBasis: PriceBasis,
)

data class BillTotals(
    val subtotal: BigDecimal,
    val taxAmount: BigDecimal,
    val chargesAmount: BigDecimal,
    val totalAmount: BigDecimal,
)

object BillMath {
    private val maxQuantity = BigDecimal("999999999.999")
    private val maxRate = BigDecimal("999999999999.9999")
    private val maxMoney = BigDecimal("999999999999.99")

    fun checked(value: BigDecimal, scale: Int, maximum: BigDecimal, positive: Boolean, field: String): BigDecimal {
        require(value <= maximum && (if (positive) value > BigDecimal.ZERO else value >= BigDecimal.ZERO)) { "$field is outside the allowed range" }
        return try {
            value.setScale(scale, RoundingMode.UNNECESSARY)
        } catch (_: ArithmeticException) {
            throw IllegalArgumentException("$field has too many decimal places")
        }
    }

    fun quantity(value: BigDecimal): BigDecimal = checked(value, 3, maxQuantity, true, "quantity")
    fun rate(value: BigDecimal): BigDecimal = checked(value, 4, maxRate, false, "unitRate")
    fun money(value: BigDecimal, field: String): BigDecimal = checked(value, 2, maxMoney, false, field)

    fun line(quantity: BigDecimal, basis: PriceBasis, unitRate: BigDecimal? = null, lineAmount: BigDecimal? = null): CalculatedLine {
        val validQuantity = BillMath.quantity(quantity)
        return when (basis) {
            PriceBasis.RATE -> {
                require(unitRate != null && lineAmount == null) { "Rate basis requires only unitRate" }
                val validRate = rate(unitRate)
                val rawAmount = validQuantity.multiply(validRate)
                require(rawAmount <= maxMoney) { "lineAmount is outside the allowed range" }
                val amount = money(rawAmount.setScale(2, RoundingMode.HALF_UP), "lineAmount")
                CalculatedLine(validQuantity, validRate, amount, basis)
            }
            PriceBasis.AMOUNT -> {
                require(lineAmount != null && unitRate == null) { "Amount basis requires only lineAmount" }
                val amount = money(lineAmount, "lineAmount")
                require(amount <= maxRate.multiply(validQuantity)) { "unitRate is outside the allowed range" }
                val derivedRate = rate(amount.divide(validQuantity, 4, RoundingMode.HALF_UP))
                CalculatedLine(validQuantity, derivedRate, amount, basis)
            }
        }
    }

    fun totals(lines: List<CalculatedLine>, taxAmount: BigDecimal? = null, chargesAmount: BigDecimal? = null): BillTotals {
        require(lines.isNotEmpty()) { "At least one line item is required" }
        val tax = money(taxAmount ?: BigDecimal.ZERO, "taxAmount")
        val charges = money(chargesAmount ?: BigDecimal.ZERO, "chargesAmount")
        val subtotal = lines.fold(BigDecimal.ZERO) { sum, line -> sum + line.lineAmount }
        val total = subtotal + tax + charges
        return BillTotals(money(subtotal, "subtotal"), tax, charges, money(total, "totalAmount"))
    }
}

data class BillLineDraft(
    val quantity: BigDecimal? = null,
    val unitRate: BigDecimal? = null,
    val lineAmount: BigDecimal? = null,
    val priceBasis: PriceBasis? = null,
) {
    fun editQuantity(value: BigDecimal?): BillLineDraft = copy(quantity = value?.let(BillMath::quantity)).recalculate()

    fun editRate(value: BigDecimal?): BillLineDraft = copy(
        unitRate = value?.let(BillMath::rate),
        lineAmount = null,
        priceBasis = if (value == null) null else PriceBasis.RATE,
    ).recalculate()

    fun editAmount(value: BigDecimal?): BillLineDraft = copy(
        unitRate = null,
        lineAmount = value?.let { BillMath.money(it, "lineAmount") },
        priceBasis = if (value == null) null else PriceBasis.AMOUNT,
    ).recalculate()

    private fun recalculate(): BillLineDraft {
        val quantity = quantity
        val basis = priceBasis
        if (quantity == null || basis == null) {
            return if (basis == PriceBasis.RATE) copy(lineAmount = null) else copy(unitRate = null)
        }
        val result = when (basis) {
            PriceBasis.RATE -> BillMath.line(quantity, basis, unitRate = unitRate)
            PriceBasis.AMOUNT -> BillMath.line(quantity, basis, lineAmount = lineAmount)
        }
        return copy(unitRate = result.unitRate, lineAmount = result.lineAmount)
    }
}
