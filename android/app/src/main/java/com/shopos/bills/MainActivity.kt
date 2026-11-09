package com.shopos.bills

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.ReceiptLong
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.shopos.bills.auth.AuthUiState
import com.shopos.bills.auth.AuthViewModel
import com.shopos.bills.data.DraftDatabase
import com.shopos.bills.employees.EmployeeController
import com.shopos.bills.employees.EmployeeScreen
import com.shopos.bills.form.BillForm
import com.shopos.bills.form.BillFormController
import com.shopos.bills.query.BillSearchController
import com.shopos.bills.query.BillSearchScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { ShopOsApp() }
    }
}

@Composable
private fun ShopOsApp(auth: AuthViewModel = viewModel()) {
    val state by auth.state.collectAsState()
    MaterialTheme {
        Surface(modifier = Modifier.fillMaxSize()) {
            if (state.user == null) {
                SignIn(state, auth::login)
            } else {
                SignedIn(state, auth)
            }
        }
    }
}

@Composable
private fun SignIn(state: AuthUiState, onSignIn: (String, String) -> Unit) {
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    val keyboardController = LocalSoftwareKeyboardController.current

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            ElevatedCard(
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(24.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    Text(
                        "ShopOS",
                        style = MaterialTheme.typography.headlineMedium,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Text(
                        "Sign in to record purchase bills",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )

                    OutlinedTextField(
                        value = username,
                        onValueChange = { username = it },
                        label = { Text("Username") },
                        leadingIcon = { Icon(Icons.Default.Person, contentDescription = null) },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                        modifier = Modifier.fillMaxWidth()
                    )

                    OutlinedTextField(
                        value = password,
                        onValueChange = { password = it },
                        label = { Text("Password") },
                        leadingIcon = { Icon(Icons.Default.Lock, contentDescription = null) },
                        singleLine = true,
                        visualTransformation = PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                        keyboardActions = KeyboardActions(onDone = {
                            keyboardController?.hide()
                            if (!state.loading && username.isNotBlank() && password.isNotBlank()) {
                                onSignIn(username, password)
                            }
                        }),
                        modifier = Modifier.fillMaxWidth()
                    )

                    if (state.error != null) {
                        OutlinedCard(
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(
                                text = state.error ?: "",
                                color = MaterialTheme.colorScheme.error,
                                style = MaterialTheme.typography.bodyMedium,
                                modifier = Modifier.padding(12.dp)
                            )
                        }
                    }

                    Button(
                        onClick = {
                            keyboardController?.hide()
                            onSignIn(username, password)
                        },
                        enabled = !state.loading && username.isNotBlank() && password.isNotBlank(),
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 8.dp)
                    ) {
                        if (state.loading) {
                            CircularProgressIndicator(
                                modifier = Modifier.padding(vertical = 2.dp),
                                color = MaterialTheme.colorScheme.onPrimary
                            )
                        } else {
                            Text("Sign in", style = MaterialTheme.typography.titleMedium)
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SignedIn(state: AuthUiState, auth: AuthViewModel) {
    val user = state.user ?: return
    val repository = remember(user.id) { auth.catalogRepository() }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val canEnter = user.canReadCatalog() && user.canCreateBill() && user.canWriteProof()
    val controller = if (canEnter) remember(user.id) { BillFormController(user.id, DraftDatabase.store(context), auth.billRepository(), scope) } else null
    val search = if (user.canReadBills()) remember(user.id) { BillSearchController(auth.billQueryRepository(), scope) } else null
    val employees = if (user.role == "owner") remember(user.id) { EmployeeController(auth.employeeRepository(), scope) } else null
    val searchState = search?.state?.collectAsState()
    var section by remember(user.id) { mutableStateOf(if (canEnter) "entry" else "search") }
    val scroll = rememberScrollState()

    LaunchedEffect(section, searchState?.value?.selectedId) { scroll.scrollTo(0) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("ShopOS", style = MaterialTheme.typography.titleLarge)
                        Text(
                            user.display_name + " (${user.role})",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                actions = {
                    IconButton(onClick = auth::logout, enabled = !state.loading) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.Logout,
                            contentDescription = "Sign out"
                        )
                    }
                }
            )
        },
        bottomBar = {
            NavigationBar {
                if (canEnter) {
                    NavigationBarItem(
                        selected = section == "entry",
                        onClick = { section = "entry" },
                        icon = { Icon(Icons.Default.ReceiptLong, contentDescription = null) },
                        label = { Text("New bill") }
                    )
                }
                if (user.canReadBills()) {
                    NavigationBarItem(
                        selected = section == "search",
                        onClick = { section = "search" },
                        icon = { Icon(Icons.Default.Search, contentDescription = null) },
                        label = { Text("Find bills") }
                    )
                }
                if (employees != null) {
                    NavigationBarItem(
                        selected = section == "employees",
                        onClick = { section = "employees" },
                        icon = { Icon(Icons.Default.People, contentDescription = null) },
                        label = { Text("Employees") }
                    )
                }
            }
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(scroll)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            if (section == "entry" && controller != null) {
                BillForm(controller, repository, user.canWriteCatalog())
            }
            if (section == "search" && search != null) {
                BillSearchScreen(search)
            }
            if (section == "employees" && employees != null) {
                EmployeeScreen(employees)
            }
            if (state.error != null) {
                OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                    Text(
                        text = state.error ?: "",
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(16.dp)
                    )
                }
            }
        }
    }
}
