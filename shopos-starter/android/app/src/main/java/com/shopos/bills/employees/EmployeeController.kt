package com.shopos.bills.employees

import com.shopos.bills.data.EmployeeCreate
import com.shopos.bills.data.EmployeeRecord
import com.shopos.bills.data.EmployeeRepository
import com.shopos.bills.data.PermissionInfo
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class EmployeeState(
    val catalog: List<PermissionInfo> = emptyList(),
    val employees: List<EmployeeRecord> = emptyList(),
    val loading: Boolean = true,
    val busy: Boolean = false,
    val error: String? = null,
    val message: String? = null,
)

class EmployeeController(private val repository: EmployeeRepository, private val scope: CoroutineScope) {
    private val mutableState = MutableStateFlow(EmployeeState())
    val state = mutableState.asStateFlow()

    init { refresh() }

    fun refresh() {
        if (mutableState.value.busy) return
        mutableState.value = mutableState.value.copy(loading = true, error = null, message = null)
        scope.launch {
            try {
                val catalog = repository.permissions()
                val employees = repository.employees()
                mutableState.value = mutableState.value.copy(catalog = catalog, employees = employees, loading = false)
            } catch (error: Exception) {
                mutableState.value = mutableState.value.copy(loading = false, error = messageFor(error))
            }
        }
    }

    private fun change(action: suspend () -> EmployeeRecord?, success: String) {
        if (mutableState.value.busy || mutableState.value.loading) return
        mutableState.value = mutableState.value.copy(busy = true, error = null, message = null)
        scope.launch {
            try {
                val updated = action()
                val employees = if (updated == null) mutableState.value.employees else {
                    val remaining = mutableState.value.employees.filterNot { it.id == updated.id }
                    (listOf(updated) + remaining).sortedBy { it.username }
                }
                mutableState.value = mutableState.value.copy(employees = employees, busy = false, message = success)
            } catch (error: Exception) {
                mutableState.value = mutableState.value.copy(busy = false, error = messageFor(error))
            }
        }
    }

    fun create(username: String, name: String, password: String, permissions: Set<String>) =
        change({ repository.create(EmployeeCreate(username, name, password, permissions.sorted())) }, "Employee created")

    fun permissions(id: String, values: Set<String>) =
        change({ repository.permissions(id, values.sorted()) }, "Permissions saved")

    fun status(id: String, active: Boolean) =
        change({ repository.status(id, active) }, if (active) "Employee activated" else "Employee deactivated")

    fun profile(id: String, name: String) =
        change({ repository.profile(id, name) }, "Name saved")

    fun password(id: String, password: String) =
        change({ repository.password(id, password); null }, "Password reset; existing sessions were signed out")

    private fun messageFor(error: Exception): String = when ((error as? HttpException)?.code()) {
        409 -> "Username already exists"
        422 -> "Check the entered values and permissions"
        403 -> "Owner access required"
        else -> error.message ?: "Request failed; check the connection"
    }
}
