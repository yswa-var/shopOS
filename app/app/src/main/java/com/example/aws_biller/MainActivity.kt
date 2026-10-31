package com.example.aws_biller

import android.app.DatePickerDialog
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.example.aws_biller.data.*
import com.example.aws_biller.ui.theme.Aws_billerTheme
import kotlinx.coroutines.launch
import java.math.BigDecimal
import java.time.LocalDate
import java.util.Calendar

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { Aws_billerTheme { BillCreatorScreen() } }
    }
}

private data class BillLineState(val item: ItemDto, val quantity: String = "1", val price: String = item.purchase_price)

@Composable
private fun BillCreatorScreen(repository: BillRepository = remember { BillRepository() }) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val focusManager = LocalFocusManager.current
    val keyboardController = LocalSoftwareKeyboardController.current
    val dismissKeyboard = { focusManager.clearFocus(); keyboardController?.hide() }
    var vendors by remember { mutableStateOf(emptyList<VendorDto>()) }
    var catalog by remember { mutableStateOf(emptyList<ItemDto>()) }
    var selectedVendor by remember { mutableStateOf<VendorDto?>(null) }
    var lines by remember { mutableStateOf(emptyList<BillLineState>()) }
    var vendorQuery by remember { mutableStateOf("") }
    var itemQuery by remember { mutableStateOf("") }
    var dueDate by remember { mutableStateOf(LocalDate.now().toString()) }
    var documentUrl by remember { mutableStateOf("") }
    var charges by remember { mutableStateOf("0.00") }
    var tax by remember { mutableStateOf("0.00") }
    var notes by remember { mutableStateOf("") }
    var loading by remember { mutableStateOf(true) }
    var saving by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var result by remember { mutableStateOf<BillDto?>(null) }
    var vendorDialog by remember { mutableStateOf(false) }
    var itemDialog by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        runCatching { repository.refreshCatalogs() }
            .onSuccess { vendors = repository.vendors; catalog = repository.items }
            .onFailure { error = "Could not load API catalogs. Check connection and try again." }
        loading = false
    }

    val subtotal = lines.fold(BigDecimal.ZERO) { acc, line ->
        acc + (line.quantity.toDecimal() * line.price.toDecimal())
    }
    val grandTotal = subtotal + charges.toDecimal() + tax.toDecimal()

    Scaffold(
        bottomBar = {
            Surface(shadowElevation = 8.dp) {
                Button(
                    enabled = !loading && !saving && selectedVendor != null && lines.isNotEmpty() && documentUrl.startsWith("https://"),
                    onClick = {
                        dismissKeyboard()
                        saving = true; error = null
                        scope.launch {
                            runCatching {
                                repository.submitAndVerify(
                                    BillCreateDto(
                                        vendor_id = selectedVendor!!.id,
                                        due_date = dueDate,
                                        document_url = documentUrl.trim(),
                                        items = lines.map { BillLineDto(it.item.id, it.quantity, it.price) },
                                        charges = charges.toDecimal().money(),
                                        tax = tax.toDecimal().money(),
                                        notes = notes.trim().ifEmpty { null },
                                    )
                                )
                            }.onSuccess { result = it }
                                .onFailure { error = it.message ?: "Bill could not be saved" }
                            saving = false
                        }
                    },
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp)
                ) { Text(if (saving) "Saving…" else "Save Bill") }
            }
        },
        modifier = Modifier.imePadding(),
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).pointerInput(Unit) { detectTapGestures { dismissKeyboard() } }.verticalScroll(rememberScrollState()).padding(20.dp)) {
            Text("New Purchase Bill", style = MaterialTheme.typography.headlineMedium)
            Spacer(Modifier.height(20.dp))
            Text("Vendor", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(vendorQuery, { vendorQuery = it }, Modifier.fillMaxWidth(), label = { Text(selectedVendor?.name ?: "Search or select vendor...") }, keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done), keyboardActions = KeyboardActions(onDone = { dismissKeyboard() }))
            vendors.filter { it.name.contains(vendorQuery, ignoreCase = true) }.take(5).forEach { vendor ->
                Text(vendor.name, Modifier.fillMaxWidth().clickable { selectedVendor = vendor; vendorQuery = "" }.padding(10.dp))
            }
            TextButton(onClick = { vendorDialog = true }) { Text("+ Add new vendor") }

            Spacer(Modifier.height(16.dp))
            Text("Items", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(itemQuery, { itemQuery = it }, Modifier.fillMaxWidth(), label = { Text("Search or add item...") }, keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done), keyboardActions = KeyboardActions(onDone = { dismissKeyboard() }))
            catalog.filter { it.name.contains(itemQuery, ignoreCase = true) }.take(5).forEach { item ->
                Text("${item.name} · ${item.unit} · ₹${item.purchase_price}", Modifier.fillMaxWidth().clickable {
                    lines = lines + BillLineState(item); itemQuery = ""
                }.padding(10.dp))
            }
            TextButton(onClick = { itemDialog = true }) { Text("+ Add new item") }

            lines.forEachIndexed { index, line ->
                Card(Modifier.fillMaxWidth().padding(vertical = 5.dp)) {
                    Column(Modifier.padding(12.dp)) {
                        Text("${line.item.name} (${line.item.unit})", style = MaterialTheme.typography.titleSmall)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedTextField(line.quantity, { value -> lines = lines.toMutableList().also { it[index] = line.copy(quantity = value) } }, Modifier.weight(1f), label = { Text("Quantity") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal, imeAction = ImeAction.Done), keyboardActions = KeyboardActions(onDone = { dismissKeyboard() }))
                            OutlinedTextField(line.price, { value -> lines = lines.toMutableList().also { it[index] = line.copy(price = value) } }, Modifier.weight(1f), label = { Text("Purchase price") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal, imeAction = ImeAction.Done), keyboardActions = KeyboardActions(onDone = { dismissKeyboard() }))
                        }
                        TextButton(onClick = { lines = lines.filterIndexed { i, _ -> i != index } }) { Text("Remove") }
                    }
                }
            }

            Spacer(Modifier.height(12.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { Text("Subtotal"); Text("₹${subtotal.money()}") }
            OutlinedTextField(charges, { charges = it }, Modifier.fillMaxWidth(), label = { Text("Charges (₹)") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal, imeAction = ImeAction.Done), keyboardActions = KeyboardActions(onDone = { dismissKeyboard() }))
            OutlinedTextField(tax, { tax = it }, Modifier.fillMaxWidth(), label = { Text("Tax (₹)") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal, imeAction = ImeAction.Done), keyboardActions = KeyboardActions(onDone = { dismissKeyboard() }))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Due date: $dueDate")
                TextButton(onClick = {
                    val now = Calendar.getInstance()
                    DatePickerDialog(context, { _, year, month, day -> dueDate = LocalDate.of(year, month + 1, day).toString() }, now.get(Calendar.YEAR), now.get(Calendar.MONTH), now.get(Calendar.DAY_OF_MONTH)).show()
                }) { Text("Select date") }
            }
            OutlinedTextField(documentUrl, { documentUrl = it }, Modifier.fillMaxWidth(), label = { Text("Document URL (https://...)") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Done), keyboardActions = KeyboardActions(onDone = { dismissKeyboard() }))
            OutlinedTextField(notes, { notes = it }, Modifier.fillMaxWidth(), label = { Text("Notes (optional)") }, keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done), keyboardActions = KeyboardActions(onDone = { dismissKeyboard() }))
            Spacer(Modifier.height(10.dp))
            Text("Grand total", style = MaterialTheme.typography.titleMedium)
            Text("₹${grandTotal.money()}", style = MaterialTheme.typography.headlineMedium)
            error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(vertical = 8.dp)) }
            if (loading) LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 8.dp))
        }
    }

    if (vendorDialog) AddVendorDialog(
        onDismiss = { vendorDialog = false },
        onSave = { name, address -> scope.launch {
            runCatching { repository.addVendor(name, address) }
                .onSuccess { vendors = repository.vendors; selectedVendor = it; vendorQuery = ""; error = null }
                .onFailure { error = it.message ?: "Vendor could not be added" }
            vendorDialog = false
        } },
    )
    if (itemDialog) AddItemDialog(
        onDismiss = { itemDialog = false },
        onSave = { name, unit, price -> scope.launch {
            runCatching { repository.addItem(name, unit, price) }
                .onSuccess { catalog = repository.items; lines = lines + BillLineState(it); itemQuery = ""; error = null }
                .onFailure { error = it.message ?: "Item could not be added" }
            itemDialog = false
        } },
    )
    result?.let { bill ->
        AlertDialog(onDismissRequest = { result = null }, confirmButton = {
            TextButton(onClick = { result = null; lines = emptyList(); selectedVendor = null; documentUrl = ""; notes = "" }) { Text("Done") }
        }, title = { Text("Bill saved") }, text = { Text("Bill #${bill.id} verified\nTotal ₹${bill.total_amount}\nBalance ₹${bill.balance_due}") })
    }
}

@Composable
private fun AddVendorDialog(onDismiss: () -> Unit, onSave: (String, String?) -> Unit) {
    var name by remember { mutableStateOf("") }; var address by remember { mutableStateOf("") }
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Add vendor") }, text = {
        Column { OutlinedTextField(name, { name = it }, label = { Text("Name") }); OutlinedTextField(address, { address = it }, label = { Text("Address (optional)") }) }
    }, confirmButton = { TextButton(enabled = name.isNotBlank(), onClick = { onSave(name, address) }) { Text("Save") } }, dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } })
}

@Composable
private fun AddItemDialog(onDismiss: () -> Unit, onSave: (String, String, String) -> Unit) {
    var name by remember { mutableStateOf("") }; var unit by remember { mutableStateOf("") }; var price by remember { mutableStateOf("") }
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Add item") }, text = {
        Column { OutlinedTextField(name, { name = it }, label = { Text("Name") }); OutlinedTextField(unit, { unit = it }, label = { Text("Unit (kg, piece…)") }); OutlinedTextField(price, { price = it }, label = { Text("Purchase price ₹") }) }
    }, confirmButton = { TextButton(enabled = name.isNotBlank() && unit.isNotBlank() && price.toDecimal() >= BigDecimal.ZERO, onClick = { onSave(name, unit, price.toDecimal().money()) }) { Text("Save") } }, dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } })
}

private fun String.toDecimal(): BigDecimal = runCatching { trim().toBigDecimal() }.getOrDefault(BigDecimal.ZERO)
private fun BigDecimal.money(): String = setScale(2, java.math.RoundingMode.HALF_UP).toPlainString()
