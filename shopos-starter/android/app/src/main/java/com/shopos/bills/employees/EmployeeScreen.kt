package com.shopos.bills.employees

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.shopos.bills.data.PermissionInfo

@Composable
fun EmployeeScreen(controller: EmployeeController) {
    val state by controller.state.collectAsState()
    var showCreate by remember { mutableStateOf(false) }
    var username by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var createGrants by remember { mutableStateOf<Set<String>?>(null) }
    var selectedId by remember { mutableStateOf<String?>(null) }
    var editName by remember { mutableStateOf("") }
    var editGrants by remember { mutableStateOf<Set<String>>(emptySet()) }
    var resetPassword by remember { mutableStateOf("") }
    var confirmDeactivate by remember { mutableStateOf(false) }
    val selected = state.employees.firstOrNull { it.id == selectedId }

    LaunchedEffect(state.catalog) {
        if (createGrants == null && state.catalog.isNotEmpty()) {
            createGrants = state.catalog.filter { it.default }.map { it.key }.toSet()
        }
    }
    LaunchedEffect(selectedId) {
        if (selected != null) {
            editName = selected.display_name
            editGrants = selected.permissions.toSet()
            resetPassword = ""
        }
    }
    LaunchedEffect(state.message) {
        if (state.message == "Employee created") {
            username = ""; name = ""; password = ""; showCreate = false
        }
        if (state.message?.startsWith("Password reset") == true) resetPassword = ""
    }

    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("Employees", style = MaterialTheme.typography.headlineSmall)
            Row {
                TextButton(onClick = controller::refresh, enabled = !state.busy) {
                    Icon(Icons.Default.Refresh, contentDescription = null, modifier = Modifier.padding(end = 4.dp))
                    Text("Refresh")
                }
                TextButton(onClick = { showCreate = !showCreate }) {
                    Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.padding(end = 4.dp))
                    Text(if (showCreate) "Cancel" else "Add")
                }
            }
        }

        if (state.loading) {
            Text("Loading employees…", style = MaterialTheme.typography.bodyMedium)
        }

        if (state.error != null) {
            OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                Text(state.error ?: "", color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(16.dp))
            }
        }

        if (state.message != null) {
            ElevatedCard(modifier = Modifier.fillMaxWidth()) {
                Text(state.message ?: "", modifier = Modifier.padding(16.dp), color = MaterialTheme.colorScheme.primary)
            }
        }

        if (showCreate) {
            ElevatedCard(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.fillMaxWidth().padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text("New Employee", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
                    OutlinedTextField(username, { username = it }, label = { Text("Username") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(name, { name = it }, label = { Text("Display name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(password, { password = it }, label = { Text("Initial password (12+ chars)") }, visualTransformation = PasswordVisualTransformation(), singleLine = true, modifier = Modifier.fillMaxWidth())
                    PermissionChecklist(state.catalog, createGrants ?: emptySet()) { createGrants = it }
                    Button(
                        onClick = { controller.create(username, name, password, createGrants ?: emptySet()) },
                        enabled = !state.busy && username.isNotBlank() && name.isNotBlank() && password.length >= 12,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(if (state.busy) "Saving…" else "Create employee")
                    }
                }
            }
        }

        state.employees.forEach { employee ->
            ElevatedCard(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 2.dp)
            ) {
                Column(
                    modifier = Modifier.fillMaxWidth().padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.Person, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                            Column {
                                Text(employee.display_name, style = MaterialTheme.typography.titleMedium)
                                Text("@${employee.username}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                        TextButton(onClick = { selectedId = if (selectedId == employee.id) null else employee.id }) {
                            Text(if (selectedId == employee.id) "Close" else "Manage")
                        }
                    }
                    Text(
                        "Status: ${if (employee.is_active) "Active" else "Inactive"}",
                        style = MaterialTheme.typography.bodySmall,
                        color = if (employee.is_active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
                    )
                }
            }
        }

        if (selected != null) {
            ElevatedCard(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.fillMaxWidth().padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    Text("Manage: ${selected.username}", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)

                    OutlinedTextField(editName, { editName = it }, label = { Text("Display name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    Button(onClick = { controller.profile(selected.id, editName) }, enabled = !state.busy && editName.isNotBlank(), modifier = Modifier.fillMaxWidth()) {
                        Text("Save display name")
                    }

                    PermissionChecklist(state.catalog, editGrants) { editGrants = it }
                    Button(onClick = { controller.permissions(selected.id, editGrants) }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) {
                        Text("Save permissions")
                    }

                    OutlinedTextField(resetPassword, { resetPassword = it }, label = { Text("New password (12+ chars)") }, visualTransformation = PasswordVisualTransformation(), singleLine = true, modifier = Modifier.fillMaxWidth())
                    Button(onClick = { controller.password(selected.id, resetPassword) }, enabled = !state.busy && resetPassword.length >= 12, modifier = Modifier.fillMaxWidth()) {
                        Text("Reset password")
                    }

                    TextButton(
                        onClick = { if (selected.is_active) confirmDeactivate = true else controller.status(selected.id, true) },
                        enabled = !state.busy,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(if (selected.is_active) "Deactivate employee" else "Activate employee", color = MaterialTheme.colorScheme.error)
                    }
                }
            }
        }

        if (confirmDeactivate && selected != null) {
            AlertDialog(
                onDismissRequest = { confirmDeactivate = false },
                title = { Text("Deactivate ${selected.username}?") },
                text = { Text("Their current sessions will end and they cannot sign in until reactivated.") },
                confirmButton = {
                    Button(onClick = { controller.status(selected.id, false); confirmDeactivate = false }) {
                        Text("Deactivate")
                    }
                },
                dismissButton = { TextButton(onClick = { confirmDeactivate = false }) { Text("Cancel") } }
            )
        }
    }
}

@Composable
private fun PermissionChecklist(catalog: List<PermissionInfo>, selected: Set<String>, onChange: (Set<String>) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text("Permissions", style = MaterialTheme.typography.titleSmall)
        catalog.forEach { permission ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Checkbox(
                    checked = permission.key in selected,
                    onCheckedChange = { checked ->
                        onChange(if (checked) selected + permission.key else selected - permission.key)
                    }
                )
                Text(permission.label, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}
