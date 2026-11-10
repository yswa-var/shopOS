package com.shopos.bills.catalog

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class CatalogPickerUiState(
    val query: String = "",
    val results: List<CatalogEntry> = emptyList(),
    val selected: CatalogEntry? = null,
    val loading: Boolean = false,
    val saving: Boolean = false,
    val error: String? = null,
    val totalCount: Int = 0,
)

class CatalogPickerState(
    private val repository: CatalogRepository,
    private val kind: CatalogKind,
    private val scope: CoroutineScope,
) {
    private val mutableState = MutableStateFlow(CatalogPickerUiState())
    val state: StateFlow<CatalogPickerUiState> = mutableState.asStateFlow()
    private val cache = linkedMapOf<String, CatalogEntry>()
    private var searchJob: Job? = null

    fun search(query: String) {
        searchJob?.cancel()
        val local = cache.values.filter { entry ->
            query.isBlank() || (listOf(entry.name) + entry.aliases).any { it.contains(query.trim(), ignoreCase = true) }
        }.take(20)
        mutableState.value = mutableState.value.copy(
            query = query,
            results = local,
            loading = true,
            error = null,
            totalCount = if (cache.isNotEmpty()) cache.size else mutableState.value.totalCount
        )
        searchJob = scope.launch {
            try {
                delay(200)
                val remote = repository.search(kind, query)
                remote.forEach { cache[it.id] = it }
                mutableState.value = mutableState.value.copy(
                    results = if (query.isBlank()) remote.take(20) else remote,
                    loading = false,
                    totalCount = cache.size
                )
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                mutableState.value = mutableState.value.copy(loading = false, error = "Search unavailable. Try again.")
            }
        }
    }

    fun select(entry: CatalogEntry) {
        mutableState.value = mutableState.value.copy(selected = entry)
    }

    fun create(name: String, aliases: List<String>, onSaved: () -> Unit) {
        if (mutableState.value.saving) return
        searchJob?.cancel()
        mutableState.value = mutableState.value.copy(saving = true, error = null)
        scope.launch {
            try {
                val entry = repository.create(kind, name, aliases)
                cache[entry.id] = entry
                mutableState.value = mutableState.value.copy(
                    selected = entry,
                    query = entry.name,
                    results = listOf(entry),
                    saving = false,
                    totalCount = cache.size
                )
                onSaved()
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: HttpException) {
                mutableState.value = mutableState.value.copy(saving = false, error = if (error.code() == 409) "Already exists. Search and select it." else "Could not save. Check the name and retry.")
            } catch (_: Exception) {
                mutableState.value = mutableState.value.copy(saving = false, error = "Could not save. Try again.")
            }
        }
    }

    fun addAlias(alias: String, onSaved: () -> Unit) {
        val selected = mutableState.value.selected ?: return
        if (mutableState.value.saving) return
        mutableState.value = mutableState.value.copy(saving = true, error = null)
        scope.launch {
            try {
                val updated = repository.addAlias(kind, selected.id, alias)
                cache[updated.id] = updated
                mutableState.value = mutableState.value.copy(selected = updated, saving = false)
                onSaved()
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: HttpException) {
                mutableState.value = mutableState.value.copy(saving = false, error = if (error.code() == 409) "Alias already belongs to an entry." else "Could not save alias. Retry.")
            } catch (_: Exception) {
                mutableState.value = mutableState.value.copy(saving = false, error = "Could not save alias. Retry.")
            }
        }
    }
}
