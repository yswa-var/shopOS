package com.shopos.bills.query

import com.shopos.bills.data.BillDetail
import com.shopos.bills.data.BillQueryRepository
import com.shopos.bills.data.BillSearchFilters
import com.shopos.bills.data.BillSearchRow
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class BillSearchState(
    val filters: BillSearchFilters = BillSearchFilters(),
    val rows: List<BillSearchRow> = emptyList(),
    val hasMore: Boolean = false,
    val loading: Boolean = false,
    val detail: BillDetail? = null,
    val selectedId: String? = null,
    val proof: ByteArray? = null,
    val proofLoading: Boolean = false,
    val error: String? = null,
)

class BillSearchController(private val repository: BillQueryRepository, private val scope: CoroutineScope) {
    private val mutableState = MutableStateFlow(BillSearchState())
    val state = mutableState.asStateFlow()
    private var generation = 0
    private var appliedFilters = BillSearchFilters()

    init { search() }

    fun filters(value: BillSearchFilters) {
        mutableState.value = mutableState.value.copy(filters = value)
    }

    fun search() {
        val current = ++generation
        val filters = mutableState.value.filters
        appliedFilters = filters
        mutableState.value = mutableState.value.copy(loading = true, error = null, rows = emptyList(), hasMore = false, selectedId = null, detail = null, proof = null)
        scope.launch {
            try {
                val result = repository.search(filters, 0)
                if (current == generation) mutableState.value = mutableState.value.copy(rows = result.rows, hasMore = result.has_more, loading = false)
            } catch (error: Exception) {
                if (current == generation) mutableState.value = mutableState.value.copy(loading = false, error = error.message ?: "Search failed")
            }
        }
    }

    fun more() {
        val currentState = mutableState.value
        if (currentState.loading || !currentState.hasMore) return
        val current = generation
        val offset = currentState.rows.size
        mutableState.value = currentState.copy(loading = true, error = null)
        scope.launch {
            try {
                val result = repository.search(appliedFilters, offset)
                if (current == generation) mutableState.value = mutableState.value.copy(rows = mutableState.value.rows + result.rows, hasMore = result.has_more, loading = false)
            } catch (error: Exception) {
                if (current == generation) mutableState.value = mutableState.value.copy(loading = false, error = error.message ?: "Could not load more bills")
            }
        }
    }

    fun select(id: String) {
        mutableState.value = mutableState.value.copy(selectedId = id, detail = null, proof = null, loading = true, error = null)
        scope.launch {
            try {
                val detail = repository.detail(id)
                if (mutableState.value.selectedId == id) mutableState.value = mutableState.value.copy(detail = detail, loading = false)
            } catch (error: Exception) {
                if (mutableState.value.selectedId == id) mutableState.value = mutableState.value.copy(loading = false, error = error.message ?: "Could not open bill")
            }
        }
    }

    fun back() {
        mutableState.value = mutableState.value.copy(selectedId = null, detail = null, proof = null, proofLoading = false, error = null)
    }

    fun proof() {
        val id = mutableState.value.detail?.proof_attachment_id ?: return
        if (mutableState.value.proofLoading) return
        mutableState.value = mutableState.value.copy(proofLoading = true, error = null)
        scope.launch {
            try {
                val bytes = repository.proof(id)
                if (mutableState.value.detail?.proof_attachment_id == id) mutableState.value = mutableState.value.copy(proof = bytes, proofLoading = false)
            } catch (error: Exception) {
                if (mutableState.value.detail?.proof_attachment_id == id) mutableState.value = mutableState.value.copy(proofLoading = false, error = error.message ?: "Could not load proof photo")
            }
        }
    }
}
