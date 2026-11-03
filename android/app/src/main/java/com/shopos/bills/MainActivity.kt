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
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.platform.LocalContext
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.shopos.bills.auth.AuthUiState
import com.shopos.bills.auth.AuthViewModel
import com.shopos.bills.data.DraftDatabase
import com.shopos.bills.form.BillForm
import com.shopos.bills.form.BillFormController

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
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("ShopOS", style = MaterialTheme.typography.headlineMedium)
        Text("Sign in to record purchase bills")
        OutlinedTextField(
            value = username,
            onValueChange = { username = it },
            label = { Text("Username") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Password") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
        )
        if (state.error != null) Text(state.error, color = MaterialTheme.colorScheme.error)
        Button(
            onClick = { onSignIn(username, password) },
            enabled = !state.loading && username.isNotBlank() && password.isNotBlank(),
            modifier = Modifier.fillMaxWidth(),
        ) {
            if (state.loading) CircularProgressIndicator() else Text("Sign in")
        }
    }
}

@Composable
private fun SignedIn(state: AuthUiState, auth: AuthViewModel) {
    val user = state.user ?: return
    val repository = remember(user.id) { auth.catalogRepository() }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val controller = remember(user.id) { BillFormController(user.id, DraftDatabase.store(context), auth.billRepository(), scope) }
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("ShopOS", style = MaterialTheme.typography.headlineMedium)
        Text("Signed in as ${user.display_name}")
        Text("Purchase bills", style = MaterialTheme.typography.titleLarge)
        if (user.canReadCatalog() && user.canCreateBill() && user.canWriteProof()) BillForm(controller, repository, user.canWriteCatalog())
        if (state.error != null) Text(state.error, color = MaterialTheme.colorScheme.error)
        TextButton(onClick = auth::logout, enabled = !state.loading) { Text("Sign out") }
    }
}
