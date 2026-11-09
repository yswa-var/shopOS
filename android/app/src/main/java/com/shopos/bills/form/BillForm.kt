package com.shopos.bills.form

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.view.LifecycleCameraController
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.shopos.bills.catalog.CatalogEntry
import com.shopos.bills.catalog.CatalogKind
import com.shopos.bills.catalog.CatalogPicker
import com.shopos.bills.catalog.CatalogRepository
import java.io.File

@Composable
fun BillForm(controller: BillFormController, catalog: CatalogRepository, canCreateCatalog: Boolean) {
    val state by controller.state.collectAsState()
    val draft = state.draft

    if (state.loading) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(32.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text("Opening draft…", style = MaterialTheme.typography.bodyLarge)
        }
        return
    }

    if (state.savedBillId != null) {
        ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(24.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Icon(
                    Icons.Default.CheckCircle,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.height(48.dp)
                )
                Text("Bill successfully saved!", style = MaterialTheme.typography.titleLarge)
                Text("Bill ID: ${state.savedBillId}", style = MaterialTheme.typography.bodyMedium)
                Button(onClick = controller::newBill, modifier = Modifier.fillMaxWidth()) {
                    Text("Record another bill")
                }
            }
        }
        return
    }

    if (draft.submitted) {
        ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Warning, contentDescription = null, tint = MaterialTheme.colorScheme.error)
                    Text("Save was sent. Retry this unchanged draft if uncertain.", style = MaterialTheme.typography.titleMedium)
                }
                Text("${draft.vendorName} · ${draft.billDate} · ${draft.lines.size} item(s) · ₹${draft.totalText()}", style = MaterialTheme.typography.bodyMedium)
                if (state.error != null) {
                    Text(state.error ?: "", color = MaterialTheme.colorScheme.error)
                }
                Button(onClick = controller::save, enabled = !state.saving, modifier = Modifier.fillMaxWidth()) {
                    Text(if (state.saving) "Checking save…" else "Retry save")
                }
            }
        }
        return
    }

    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("New Purchase Bill", style = MaterialTheme.typography.headlineSmall)

        // Vendor & Date Section
        ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                key(draft.idempotencyKey) {
                    CatalogPicker(
                        label = BillFormFields.header.field("vendor_id").label,
                        kind = CatalogKind.VENDOR,
                        repository = catalog,
                        canCreate = canCreateCatalog,
                        selected = draft.vendorId.takeIf { it.isNotBlank() }?.let { CatalogEntry(it, draft.vendorName, emptyList()) },
                        onSelected = controller::vendor,
                    )
                }
                FormText(BillFormFields.header.field("bill_date"), draft.billDate, controller::billDate)
            }
        }

        // Line Items Section
        Text("Items (${draft.lines.size})", style = MaterialTheme.typography.titleMedium)

        draft.lines.forEachIndexed { index, line ->
            key(line.localId) {
                ElevatedCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.fillMaxWidth().padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text("Item #${index + 1}", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.primary)
                            if (draft.lines.size > 1) {
                                TextButton(onClick = { controller.removeLine(line.localId) }) {
                                    Icon(Icons.Default.Delete, contentDescription = null, modifier = Modifier.padding(end = 4.dp))
                                    Text("Remove")
                                }
                            }
                        }

                        CatalogPicker(
                            label = BillFormFields.lineItem.field("item_id").label,
                            kind = CatalogKind.ITEM,
                            repository = catalog,
                            canCreate = canCreateCatalog,
                            selected = line.itemId.takeIf { it.isNotBlank() }?.let { CatalogEntry(it, line.itemName, emptyList()) },
                            onSelected = { selected -> controller.line(line.localId) { it.copy(itemId = selected.id, itemName = selected.name) } },
                        )

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            BoxModifierScope(Modifier.weight(1f)) {
                                FormText(BillFormFields.lineItem.field("quantity"), line.quantity) { value ->
                                    controller.line(line.localId) { it.withQuantity(value) }
                                }
                            }
                            BoxModifierScope(Modifier.weight(1f)) {
                                FormText(BillFormFields.lineItem.field("unit_rate"), line.unitRate) { value ->
                                    controller.line(line.localId) { it.withRate(value) }
                                }
                            }
                        }

                        FormText(BillFormFields.lineItem.field("line_amount"), line.lineAmount) { value ->
                            controller.line(line.localId) { it.withAmount(value) }
                        }

                        Text(
                            "Basis: ${if (line.priceBasis == "rate") "Rate" else "Amount"} (other is auto-calculated)",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
        }

        Button(
            onClick = controller::addLine,
            modifier = Modifier.fillMaxWidth()
        ) {
            Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.padding(end = 4.dp))
            Text("Add another item")
        }

        // Taxes & Charges Section
        ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text("Additional Details", style = MaterialTheme.typography.titleSmall)
                FormText(BillFormFields.header.field("tax_amount"), draft.taxAmount, controller::tax)
                FormText(BillFormFields.header.field("charges_amount"), draft.chargesAmount, controller::charges)
            }
        }

        // Summary Card
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
                Text("₹${draft.totalText()}", style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onPrimaryContainer)
            }
        }

        // Proof Capture Section
        ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                ProofCapture(draft.proofPath, controller::photo)
            }
        }

        if (state.error != null) {
            OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                Text(state.error ?: "", color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(16.dp))
            }
        }

        Button(
            onClick = controller::save,
            enabled = !state.saving,
            modifier = Modifier.fillMaxWidth().height(50.dp)
        ) {
            Text(if (state.saving) "Uploading and saving…" else "Save bill", style = MaterialTheme.typography.titleMedium)
        }

        Text(
            "Draft saved locally on device. Keep connected to sync.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(bottom = 24.dp)
        )
    }
}

@Composable
private fun BoxModifierScope(modifier: Modifier, content: @Composable () -> Unit) {
    Column(modifier = modifier) { content() }
}

private fun List<BillFieldSpec>.field(key: String) = first { it.key == key }

@Composable
private fun FormText(field: BillFieldSpec, value: String, onChange: (String) -> Unit) {
    if (!field.visible) return
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        label = { Text(field.label + if (field.required) " *" else "") },
        keyboardOptions = KeyboardOptions(keyboardType = if (field.kind == BillInputKind.DECIMAL || field.kind == BillInputKind.MONEY) KeyboardType.Decimal else KeyboardType.Text),
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun ProofCapture(path: String?, onPhoto: (File) -> Unit) {
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current
    var open by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) open = true else error = "Camera permission is required for proof photo"
    }

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(BillFormFields.header.field("proof_photo").label + " *", style = MaterialTheme.typography.titleSmall)
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    if (path != null && File(path).isFile) Icons.Default.CheckCircle else Icons.Default.PhotoCamera,
                    contentDescription = null,
                    tint = if (path != null && File(path).isFile) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.height(18.dp)
                )
                Text(
                    if (path != null && File(path).isFile) "Photo ready" else "Photo required",
                    style = MaterialTheme.typography.bodySmall,
                    color = if (path != null && File(path).isFile) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
        Button(
            onClick = {
                if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) open = true
                else permission.launch(Manifest.permission.CAMERA)
            }
        ) {
            Icon(Icons.Default.PhotoCamera, contentDescription = null, modifier = Modifier.padding(end = 4.dp))
            Text(if (path == null) "Take photo" else "Retake")
        }
    }

    if (error != null) {
        Text(error ?: "", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
    }

    if (open) {
        val camera = remember(context) { LifecycleCameraController(context).apply { setEnabledUseCases(LifecycleCameraController.IMAGE_CAPTURE) } }
        DisposableEffect(camera, lifecycle) {
            camera.bindToLifecycle(lifecycle)
            onDispose { camera.unbind() }
        }
        OutlinedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                AndroidView(
                    factory = { PreviewView(it).apply { controller = camera } },
                    modifier = Modifier.fillMaxWidth().height(280.dp)
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    TextButton(onClick = { open = false }) { Text("Cancel") }
                    Button(onClick = {
                        val file = File.createTempFile("bill-proof-", ".jpg", context.filesDir)
                        camera.takePicture(
                            ImageCapture.OutputFileOptions.Builder(file).build(),
                            ContextCompat.getMainExecutor(context),
                            object : ImageCapture.OnImageSavedCallback {
                                override fun onImageSaved(output: ImageCapture.OutputFileResults) {
                                    onPhoto(file)
                                    open = false
                                }
                                override fun onError(exception: ImageCaptureException) {
                                    file.delete()
                                    error = exception.message
                                }
                            }
                        )
                    }) {
                        Text("Capture Photo")
                    }
                }
            }
        }
    }
}
