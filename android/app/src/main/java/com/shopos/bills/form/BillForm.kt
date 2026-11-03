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
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
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
    if (state.loading) { Text("Opening draft…"); return }
    if (state.savedBillId != null) {
        Text("Bill saved: ${state.savedBillId}", style = MaterialTheme.typography.titleMedium)
        Button(onClick = controller::newBill) { Text("Record another bill") }
        return
    }
    if (draft.submitted) {
        Text("Save was sent. Retry this unchanged draft if the result is uncertain.")
        Text("${draft.vendorName} · ${draft.billDate} · ${draft.lines.size} item(s) · ₹${draft.totalText()}")
        if (state.error != null) Text(state.error ?: "", color = MaterialTheme.colorScheme.error)
        Button(onClick = controller::save, enabled = !state.saving) { Text(if (state.saving) "Checking save…" else "Retry save") }
        return
    }
    Text("New purchase bill", style = MaterialTheme.typography.titleLarge)
    key(draft.idempotencyKey) { CatalogPicker(
        label = BillFormFields.header.field("vendor_id").label,
        kind = CatalogKind.VENDOR,
        repository = catalog,
        canCreate = canCreateCatalog,
        selected = draft.vendorId.takeIf { it.isNotBlank() }?.let { CatalogEntry(it, draft.vendorName, emptyList()) },
        onSelected = controller::vendor,
    ) }
    FormText(BillFormFields.header.field("bill_date"), draft.billDate, controller::billDate)
    draft.lines.forEachIndexed { index, line ->
        key(line.localId) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Item ${index + 1}", style = MaterialTheme.typography.titleMedium)
                if (draft.lines.size > 1) TextButton(onClick = { controller.removeLine(line.localId) }) { Text("Remove") }
            }
            CatalogPicker(
                label = BillFormFields.lineItem.field("item_id").label,
                kind = CatalogKind.ITEM,
                repository = catalog,
                canCreate = canCreateCatalog,
                selected = line.itemId.takeIf { it.isNotBlank() }?.let { CatalogEntry(it, line.itemName, emptyList()) },
                onSelected = { selected -> controller.line(line.localId) { it.copy(itemId = selected.id, itemName = selected.name) } },
            )
            FormText(BillFormFields.lineItem.field("quantity"), line.quantity) { value ->
                controller.line(line.localId) { it.withQuantity(value) }
            }
            FormText(BillFormFields.lineItem.field("unit_rate"), line.unitRate) { value ->
                controller.line(line.localId) { it.withRate(value) }
            }
            FormText(BillFormFields.lineItem.field("line_amount"), line.lineAmount) { value ->
                controller.line(line.localId) { it.withAmount(value) }
            }
            Text("Editing ${if (line.priceBasis == "rate") "rate" else "amount"}; the other value is calculated")
        }
        }
    }
    TextButton(onClick = controller::addLine) { Text("Add another item") }
    FormText(BillFormFields.header.field("tax_amount"), draft.taxAmount, controller::tax)
    FormText(BillFormFields.header.field("charges_amount"), draft.chargesAmount, controller::charges)
    Text("Total: ₹${draft.totalText()}", style = MaterialTheme.typography.titleMedium)
    ProofCapture(draft.proofPath, controller::photo)
    if (state.error != null) Text(state.error ?: "", color = MaterialTheme.colorScheme.error)
    Button(onClick = controller::save, enabled = !state.saving, modifier = Modifier.fillMaxWidth()) {
        Text(if (state.saving) "Uploading and saving…" else "Save bill")
    }
    Text("Draft saved on this device. Keep online to save the bill.")
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
        if (granted) open = true else error = "Camera permission is required for the proof photo"
    }
    Text(BillFormFields.header.field("proof_photo").label + " *")
    if (path != null) Text(if (File(path).isFile) "Photo ready" else "Photo missing; take another")
    TextButton(onClick = {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) open = true
        else permission.launch(Manifest.permission.CAMERA)
    }) { Text(if (path == null) "Take photo" else "Retake photo") }
    if (error != null) Text(error ?: "", color = MaterialTheme.colorScheme.error)
    if (open) {
        val camera = remember(context) { LifecycleCameraController(context).apply { setEnabledUseCases(LifecycleCameraController.IMAGE_CAPTURE) } }
        DisposableEffect(camera, lifecycle) {
            camera.bindToLifecycle(lifecycle)
            onDispose { camera.unbind() }
        }
        AndroidView(factory = { PreviewView(it).apply { controller = camera } }, modifier = Modifier.fillMaxWidth().height(320.dp))
        Row {
            Button(onClick = {
                val file = File.createTempFile("bill-proof-", ".jpg", context.filesDir)
                camera.takePicture(ImageCapture.OutputFileOptions.Builder(file).build(), ContextCompat.getMainExecutor(context),
                    object : ImageCapture.OnImageSavedCallback {
                        override fun onImageSaved(output: ImageCapture.OutputFileResults) { onPhoto(file); open = false }
                        override fun onError(exception: ImageCaptureException) { file.delete(); error = exception.message }
                    })
            }) { Text("Capture") }
            TextButton(onClick = { open = false }) { Text("Cancel") }
        }
    }
}
