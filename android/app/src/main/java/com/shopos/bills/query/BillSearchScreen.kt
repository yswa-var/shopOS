package com.shopos.bills.query

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp

@Composable
fun BillSearchScreen(controller: BillSearchController) {
    val state by controller.state.collectAsState()
    val detail = state.detail
    if (state.selectedId != null) {
        TextButton(onClick = controller::back) { Text("Back to results") }
        if (state.loading) Text("Opening bill…")
        if (state.error != null) Text(state.error ?: "", color = MaterialTheme.colorScheme.error)
        if (detail != null) {
            Text(detail.vendor_name, style = MaterialTheme.typography.titleLarge)
            Text("${detail.bill_date} · recorded by ${detail.employee_name}")
            detail.items.forEach { line ->
                Text("${line.item_name}: ${line.quantity} × ₹${line.unit_rate} = ₹${line.line_amount}")
                Text("Entered by ${if (line.price_basis == "rate") "rate" else "amount"}", style = MaterialTheme.typography.bodySmall)
            }
            Text("Subtotal ₹${detail.subtotal}")
            Text("Tax ₹${detail.tax_amount} · Extra charges ₹${detail.charges_amount}")
            Text("Total ₹${detail.total_amount}", style = MaterialTheme.typography.titleMedium)
            TextButton(onClick = controller::proof, enabled = !state.proofLoading) {
                Text(if (state.proofLoading) "Loading proof…" else "View proof photo")
            }
            val bitmap = remember(state.proof) { state.proof?.let(::decodePreview) }
            if (state.proof != null && bitmap == null) Text("Could not display proof photo")
            if (bitmap != null) Image(bitmap.asImageBitmap(), contentDescription = "Bill proof photo", contentScale = ContentScale.Fit, modifier = Modifier.fillMaxWidth().height(320.dp))
        }
        return
    }

    Text("Find purchase bills", style = MaterialTheme.typography.titleLarge)
    FilterField("Vendor name or alias", state.filters.vendor) { controller.filters(state.filters.copy(vendor = it)) }
    FilterField("Item name or alias", state.filters.item) { controller.filters(state.filters.copy(item = it)) }
    FilterField("Employee name", state.filters.employee) { controller.filters(state.filters.copy(employee = it)) }
    FilterField("From date (YYYY-MM-DD)", state.filters.dateFrom) { controller.filters(state.filters.copy(dateFrom = it)) }
    FilterField("To date (YYYY-MM-DD)", state.filters.dateTo) { controller.filters(state.filters.copy(dateTo = it)) }
    FilterField("Minimum total (₹)", state.filters.amountMin, true) { controller.filters(state.filters.copy(amountMin = it)) }
    FilterField("Maximum total (₹)", state.filters.amountMax, true) { controller.filters(state.filters.copy(amountMax = it)) }
    Button(onClick = controller::search, modifier = Modifier.fillMaxWidth()) { Text("Search") }
    if (state.loading) Text("Loading bills…")
    if (state.error != null) Text(state.error ?: "", color = MaterialTheme.colorScheme.error)
    if (!state.loading && state.rows.isEmpty() && state.error == null) Text("No matching bills")
    state.rows.forEach { bill ->
        Column(modifier = Modifier.fillMaxWidth().clickable { controller.select(bill.id) }.padding(vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("${bill.vendor_name} · ₹${bill.total_amount}", style = MaterialTheme.typography.titleMedium)
            Text("${bill.bill_date} · ${bill.employee_name}")
            Text(bill.item_names.joinToString(), style = MaterialTheme.typography.bodySmall)
        }
    }
    if (state.hasMore) TextButton(onClick = controller::more, enabled = !state.loading) { Text("Load more") }
}

@Composable
private fun FilterField(label: String, value: String, decimal: Boolean = false, onChange: (String) -> Unit) {
    OutlinedTextField(value, onChange, label = { Text(label) }, singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = if (decimal) KeyboardType.Decimal else KeyboardType.Text),
        modifier = Modifier.fillMaxWidth())
}

private fun decodePreview(bytes: ByteArray): Bitmap? {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
    var sample = 1
    while (bounds.outWidth / sample > 1600 || bounds.outHeight / sample > 1600) sample *= 2
    return BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply { inSampleSize = sample })
}
