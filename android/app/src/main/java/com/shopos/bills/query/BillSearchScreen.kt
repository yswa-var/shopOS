package com.shopos.bills.query

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
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
        Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
            TextButton(onClick = controller::back) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null, modifier = Modifier.padding(end = 4.dp))
                Text("Back to results")
            }

            if (state.loading) {
                Text("Opening bill…", style = MaterialTheme.typography.bodyLarge)
            }

            if (state.error != null) {
                OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                    Text(state.error ?: "", color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(16.dp))
                }
            }

            if (detail != null) {
                ElevatedCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.fillMaxWidth().padding(20.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Text(detail.vendor_name, style = MaterialTheme.typography.headlineSmall)
                        Text(
                            "${detail.bill_date} · Recorded by ${detail.employee_name}",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )

                        HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))

                        Text("Items", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.primary)
                        detail.items.forEach { line ->
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(line.item_name, style = MaterialTheme.typography.bodyMedium)
                                    Text(
                                        "${line.quantity} × ₹${line.unit_rate} (${if (line.price_basis == "rate") "Rate" else "Amount"})",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                Text("₹${line.line_amount}", style = MaterialTheme.typography.titleMedium)
                            }
                        }

                        HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))

                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("Subtotal", style = MaterialTheme.typography.bodyMedium)
                            Text("₹${detail.subtotal}", style = MaterialTheme.typography.bodyMedium)
                        }
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("Tax & Charges", style = MaterialTheme.typography.bodyMedium)
                            Text("₹${detail.tax_amount} + ₹${detail.charges_amount}", style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }

                ElevatedCard(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.elevatedCardColors(
                        containerColor = MaterialTheme.colorScheme.primaryContainer
                    )
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(16.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("Total Amount", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onPrimaryContainer)
                        Text("₹${detail.total_amount}", style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onPrimaryContainer)
                    }
                }

                ElevatedCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.fillMaxWidth().padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Text("Proof Photo", style = MaterialTheme.typography.titleSmall)
                        TextButton(onClick = controller::proof, enabled = !state.proofLoading, modifier = Modifier.fillMaxWidth()) {
                            Icon(Icons.Default.Image, contentDescription = null, modifier = Modifier.padding(end = 4.dp))
                            Text(if (state.proofLoading) "Loading proof…" else "View proof photo")
                        }

                        val bitmap = remember(state.proof) { state.proof?.let(::decodePreview) }
                        if (state.proof != null && bitmap == null) {
                            Text("Could not display proof photo", color = MaterialTheme.colorScheme.error)
                        }
                        if (bitmap != null) {
                            Image(
                                bitmap.asImageBitmap(),
                                contentDescription = "Bill proof photo",
                                contentScale = ContentScale.Fit,
                                modifier = Modifier.fillMaxWidth().height(320.dp)
                            )
                        }
                    }
                }
            }
        }
        return
    }

    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("Find Purchase Bills", style = MaterialTheme.typography.headlineSmall)

        ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text("Search Filters", style = MaterialTheme.typography.titleSmall)
                FilterField("Vendor name or alias", state.filters.vendor) { controller.filters(state.filters.copy(vendor = it)) }
                FilterField("Item name or alias", state.filters.item) { controller.filters(state.filters.copy(item = it)) }
                FilterField("Employee name", state.filters.employee) { controller.filters(state.filters.copy(employee = it)) }
                FilterField("From date (YYYY-MM-DD)", state.filters.dateFrom) { controller.filters(state.filters.copy(dateFrom = it)) }
                FilterField("To date (YYYY-MM-DD)", state.filters.dateTo) { controller.filters(state.filters.copy(dateTo = it)) }
                FilterField("Minimum total (₹)", state.filters.amountMin, true) { controller.filters(state.filters.copy(amountMin = it)) }
                FilterField("Maximum total (₹)", state.filters.amountMax, true) { controller.filters(state.filters.copy(amountMax = it)) }

                Button(
                    onClick = controller::search,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(Icons.Default.Search, contentDescription = null, modifier = Modifier.padding(end = 4.dp))
                    Text("Search")
                }
            }
        }

        if (state.loading) {
            Text("Loading bills…", style = MaterialTheme.typography.bodyMedium)
        }

        if (state.error != null) {
            OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                Text(state.error ?: "", color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(16.dp))
            }
        }

        if (!state.loading && state.rows.isEmpty() && state.error == null) {
            Text("No matching bills found", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }

        state.rows.forEach { bill ->
            ElevatedCard(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { controller.select(bill.id) }
            ) {
                Column(
                    modifier = Modifier.fillMaxWidth().padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(bill.vendor_name, style = MaterialTheme.typography.titleMedium)
                        Text("₹${bill.total_amount}", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
                    }
                    Text(
                        "${bill.bill_date} · By ${bill.employee_name}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    if (bill.item_names.isNotEmpty()) {
                        Text(
                            bill.item_names.joinToString(),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
        }

        if (state.hasMore) {
            Button(
                onClick = controller::more,
                enabled = !state.loading,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Load more")
            }
        }
    }
}

@Composable
private fun FilterField(label: String, value: String, decimal: Boolean = false, onChange: (String) -> Unit) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        label = { Text(label) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = if (decimal) KeyboardType.Decimal else KeyboardType.Text),
        modifier = Modifier.fillMaxWidth()
    )
}

private fun decodePreview(bytes: ByteArray): Bitmap? {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
    var sample = 1
    while (bounds.outWidth / sample > 1600 || bounds.outHeight / sample > 1600) sample *= 2
    return BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply { inSampleSize = sample })
}
