package com.shopos.bills.domain

import java.math.BigDecimal
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class BillMathTest {
    private fun d(value: String) = BigDecimal(value)

    @Test fun quantityKeepsLatestPricingBasis() {
        val rateDraft = BillLineDraft().editRate(d("12.3456")).editQuantity(d("2"))
        assertEquals(d("24.69"), rateDraft.lineAmount)
        val changedQuantity = rateDraft.editQuantity(d("3"))
        assertEquals(d("12.3456"), changedQuantity.unitRate)
        assertEquals(d("37.04"), changedQuantity.lineAmount)
        val amountDraft = changedQuantity.editAmount(d("100.00")).editQuantity(d("6"))
        assertEquals(PriceBasis.AMOUNT, amountDraft.priceBasis)
        assertEquals(d("100.00"), amountDraft.lineAmount)
        assertEquals(d("16.6667"), amountDraft.unitRate)
        assertEquals(d("51.00"), amountDraft.editRate(d("8.50")).lineAmount)
    }

    @Test fun halfUpRoundingAndOptionalExtras() {
        val first = BillMath.line(d("1"), PriceBasis.RATE, unitRate = d("0.005"))
        val second = BillMath.line(d("3"), PriceBasis.AMOUNT, lineAmount = d("100.00"))
        assertEquals(d("0.01"), first.lineAmount)
        assertEquals(d("33.3333"), second.unitRate)
        assertEquals(d("100.01"), BillMath.totals(listOf(first, second)).totalAmount)
        assertEquals(d("106.76"), BillMath.totals(listOf(first, second), d("5.50"), d("1.25")).totalAmount)
    }

    @Test fun amountFirstSurvivesQuantityChangeAndClear() {
        val draft = BillLineDraft().editAmount(d("0.01")).editQuantity(d("999999999.999"))
        assertEquals(d("0.01"), draft.lineAmount)
        assertEquals(d("0.0000"), draft.unitRate)
        val cleared = draft.editQuantity(null)
        assertEquals(d("0.01"), cleared.lineAmount)
        assertEquals(null, cleared.unitRate)
    }

    @Test fun invalidQuantityAndMoneyAreRejected() {
        assertThrows(IllegalArgumentException::class.java) { BillMath.line(d("0"), PriceBasis.RATE, unitRate = d("1")) }
        assertThrows(IllegalArgumentException::class.java) { BillMath.line(d("1.0001"), PriceBasis.RATE, unitRate = d("1")) }
        assertThrows(IllegalArgumentException::class.java) { BillMath.line(d("1"), PriceBasis.AMOUNT, lineAmount = d("-0.01")) }
        assertThrows(IllegalArgumentException::class.java) { BillMath.totals(emptyList()) }
    }
}
