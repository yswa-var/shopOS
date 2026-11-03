package com.shopos.bills.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import com.shopos.bills.catalog.CatalogRepository
import com.shopos.bills.catalog.catalogRepository

data class AuthUiState(
    val user: UserResponse? = null,
    val loading: Boolean = false,
    val error: String? = null,
)

class AuthViewModel : ViewModel() {
    private val repository = authRepository()
    private val mutableState = MutableStateFlow(AuthUiState())
    val state: StateFlow<AuthUiState> = mutableState.asStateFlow()
    private var token: String? = null

    fun catalogRepository(): CatalogRepository = catalogRepository { token }

    fun login(username: String, password: String) {
        if (mutableState.value.loading) return
        mutableState.value = AuthUiState(loading = true)
        viewModelScope.launch {
            try {
                val (newToken, user) = repository.login(username, password)
                token = newToken
                mutableState.value = AuthUiState(user = user)
            } catch (_: Exception) {
                mutableState.value = AuthUiState(error = "Could not sign in. Check your details and connection.")
            }
        }
    }

    fun logout() {
        val currentToken = token ?: return
        if (mutableState.value.loading) return
        mutableState.value = mutableState.value.copy(loading = true, error = null)
        viewModelScope.launch {
            try {
                repository.logout(currentToken)
                token = null
                mutableState.value = AuthUiState()
            } catch (_: Exception) {
                mutableState.value = mutableState.value.copy(loading = false, error = "Could not sign out. Please retry.")
            }
        }
    }
}
