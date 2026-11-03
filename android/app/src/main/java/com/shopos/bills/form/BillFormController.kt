package com.shopos.bills.form

import com.shopos.bills.catalog.CatalogEntry
import com.shopos.bills.data.BillDraftStore
import com.shopos.bills.data.BillRepository
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

data class BillFormState(
    val draft: BillDraftSnapshot = BillDraftSnapshot(),
    val loading: Boolean = true,
    val saving: Boolean = false,
    val savedBillId: String? = null,
    val error: String? = null,
)

class BillFormController(
    private val userId: String,
    private val store: BillDraftStore,
    private val repository: BillRepository,
    private val scope: CoroutineScope,
) {
    private val writeMutex = Mutex()
    private val saveMutex = Mutex()
    private val mutableState = MutableStateFlow(BillFormState())
    val state = mutableState.asStateFlow()

    init {
        scope.launch {
            try {
                val restored = store.load(userId) ?: BillDraftSnapshot()
                mutableState.value = BillFormState(draft = restored, loading = false)
                persist()
            } catch (error: Exception) {
                mutableState.value = mutableState.value.copy(loading = false, error = "Could not open local draft: ${error.message}")
            }
        }
    }

    private fun change(edit: (BillDraftSnapshot) -> BillDraftSnapshot) {
        val current = mutableState.value
        if (current.loading || current.saving || current.savedBillId != null || current.draft.submitted) return
        mutableState.value = current.copy(draft = edit(current.draft), error = null)
        scope.launch { persist() }
    }

    private suspend fun persist() = writeMutex.withLock {
        if (mutableState.value.savedBillId == null) store.save(userId, mutableState.value.draft)
    }

    fun vendor(entry: CatalogEntry) = change { it.copy(vendorId = entry.id, vendorName = entry.name) }
    fun billDate(value: String) = change { it.copy(billDate = value) }
    fun tax(value: String) = change { it.copy(taxAmount = value) }
    fun charges(value: String) = change { it.copy(chargesAmount = value) }
    fun addLine() = change { it.copy(lines = it.lines + BillLineSnapshot()) }
    fun removeLine(localId: String) = change { draft ->
        if (draft.lines.size == 1) draft else draft.copy(lines = draft.lines.filterNot { it.localId == localId })
    }
    fun line(localId: String, edit: (BillLineSnapshot) -> BillLineSnapshot) = change { draft ->
        draft.copy(lines = draft.lines.map { if (it.localId == localId) edit(it) else it })
    }
    fun photo(file: File) = change { it.copy(proofPath = file.absolutePath, proofAttachmentId = null, proofUploadId = java.util.UUID.randomUUID().toString()) }

    fun save() {
        if (mutableState.value.loading || mutableState.value.saving || mutableState.value.savedBillId != null) return
        scope.launch {
            saveMutex.withLock {
                val draft = mutableState.value.draft
                try {
                    // Validate the full form before uploading a photo.
                    draft.request(draft.proofAttachmentId ?: java.util.UUID.randomUUID().toString())
                    mutableState.value = mutableState.value.copy(saving = true, error = null)
                    persist()
                    val proofId = draft.proofAttachmentId ?: repository.upload(File(draft.proofPath!!), draft.proofUploadId).also {
                        mutableState.value = mutableState.value.copy(draft = draft.copy(proofAttachmentId = it))
                        persist()
                    }
                    // Once sent, retries must use byte-for-byte equivalent form data.
                    mutableState.value = mutableState.value.copy(draft = mutableState.value.draft.copy(submitted = true))
                    persist()
                    val saved = repository.create(mutableState.value.draft.request(proofId))
                    writeMutex.withLock {
                        mutableState.value = mutableState.value.copy(saving = false, savedBillId = saved.id)
                        store.delete(userId)
                    }
                    File(draft.proofPath!!).delete()
                } catch (error: Exception) {
                    mutableState.value = mutableState.value.copy(saving = false, error = error.message ?: "Could not save bill")
                }
            }
        }
    }

    fun newBill() {
        val state = mutableState.value
        if (state.savedBillId == null) return
        mutableState.value = BillFormState(draft = BillDraftSnapshot(), loading = false)
        scope.launch { persist() }
    }
}
