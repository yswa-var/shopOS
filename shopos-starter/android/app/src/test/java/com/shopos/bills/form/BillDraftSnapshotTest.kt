package com.shopos.bills.form

import com.google.gson.Gson
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class BillDraftSnapshotTest {
    @Test fun multiItemDraftRestoresAndKeepsRetryIds() {
        val photo = File.createTempFile("shopos-test-photo", ".jpg")
        try {
            photo.writeBytes(byteArrayOf(0xff.toByte(), 0xd8.toByte(), 0xff.toByte()))
            val first = BillLineSnapshot(itemId = "item-one", itemName = "Tea").withRate("12.50").withQuantity("2")
            val second = BillLineSnapshot(itemId = "item-two", itemName = "Milk").withAmount("7.00")
            val draft = BillDraftSnapshot(vendorId = "vendor-one", vendorName = "Supplier", lines = listOf(first, second), taxAmount = "1.50", proofPath = photo.absolutePath)
            val restored = Gson().fromJson(Gson().toJson(draft), BillDraftSnapshot::class.java)
            assertEquals(draft, restored)
            assertEquals("33.50", restored.totalText())
            assertEquals(draft.idempotencyKey, restored.request("proof-one").idempotency_key)
            assertEquals(draft.proofUploadId, restored.proofUploadId)
            assertEquals("12.5000", restored.request("proof-one").items[0].unit_rate)
            assertEquals("7.00", restored.request("proof-one").items[1].line_amount)
            assertEquals(null, restored.request("proof-one").items[1].unit_rate)
            assertNotEquals(draft.idempotencyKey, BillDraftSnapshot().idempotencyKey)
        } finally { photo.delete() }
    }
}
