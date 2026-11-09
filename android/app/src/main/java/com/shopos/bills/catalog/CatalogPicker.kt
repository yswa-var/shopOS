package com.shopos.bills.catalog

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AlertDialog
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/** Shared selector for the bill form; it only reports a selected catalog record. */
@Composable
fun CatalogPicker(
    label: String,
    kind: CatalogKind,
    repository: CatalogRepository,
    canCreate: Boolean,
    selected: CatalogEntry? = null,
    onSelected: (CatalogEntry) -> Unit,
) {
    val scope = rememberCoroutineScope()
    val picker = remember(repository, kind) { CatalogPickerState(repository, kind, scope) }
    val state by picker.state.collectAsState()
    var showCreate by remember { mutableStateOf(false) }
    var showAlias by remember { mutableStateOf(false) }

    LaunchedEffect(picker) { picker.search("") }
    LaunchedEffect(picker, selected?.id) { if (selected != null) picker.select(selected) }

    Column(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
        Text(label, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.primary)

        if (state.selected != null) {
            ElevatedCard(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.elevatedCardColors(
                    containerColor = MaterialTheme.colorScheme.secondaryContainer
                )
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(12.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.CheckCircle, contentDescription = null, tint = MaterialTheme.colorScheme.onSecondaryContainer)
                    Text(
                        "Selected: ${state.selected?.name}",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSecondaryContainer
                    )
                }
            }
        }

        OutlinedTextField(
            value = state.query,
            onValueChange = picker::search,
            label = { Text("Search $label") },
            leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )

        if (state.loading) {
            Text("Searching…", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }

        if (state.results.isNotEmpty()) {
            OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.fillMaxWidth().padding(4.dp)) {
                    state.results.take(5).forEach { entry ->
                        Text(
                            text = entry.name + if (entry.aliases.isEmpty()) "" else " · ${entry.aliases.joinToString()}",
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    picker.select(entry)
                                    onSelected(entry)
                                }
                                .padding(horizontal = 12.dp, vertical = 10.dp),
                        )
                    }
                }
            }
        }

        if (state.error != null) {
            Text(state.error ?: "", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        }

        if (canCreate) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = { showCreate = true }) {
                    Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.padding(end = 4.dp))
                    Text("Add $label")
                }
                if (state.selected != null) {
                    TextButton(onClick = { showAlias = true }) { Text("Add alias") }
                }
            }
        }
    }

    if (showCreate) {
        CreateEntryDialog(label, state.saving, state.error, onDismiss = { showCreate = false }) { name, aliases ->
            picker.create(name, aliases) {
                picker.state.value.selected?.let(onSelected)
                showCreate = false
            }
        }
    }
    if (showAlias) {
        AddAliasDialog(state.saving, state.error, onDismiss = { showAlias = false }) { alias ->
            picker.addAlias(alias) {
                picker.state.value.selected?.let(onSelected)
                showAlias = false
            }
        }
    }
}

@Composable
private fun CreateEntryDialog(label: String, saving: Boolean, error: String?, onDismiss: () -> Unit, onSave: (String, List<String>) -> Unit) {
    var name by remember { mutableStateOf("") }
    var aliases by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Add $label") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(name, { name = it }, label = { Text("Name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(aliases, { aliases = it }, label = { Text("Aliases (comma separated)") }, modifier = Modifier.fillMaxWidth())
                if (error != null) Text(error, color = MaterialTheme.colorScheme.error)
            }
        },
        confirmButton = {
            Button(
                onClick = { onSave(name, aliases.split(',').map { it.trim() }.filter { it.isNotEmpty() }) },
                enabled = !saving && name.isNotBlank(),
            ) { Text("Save") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun AddAliasDialog(saving: Boolean, error: String?, onDismiss: () -> Unit, onSave: (String) -> Unit) {
    var alias by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Add alias") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(alias, { alias = it }, label = { Text("Alias") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                if (error != null) Text(error, color = MaterialTheme.colorScheme.error)
            }
        },
        confirmButton = { Button(onClick = { onSave(alias) }, enabled = !saving && alias.isNotBlank()) { Text("Save") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
