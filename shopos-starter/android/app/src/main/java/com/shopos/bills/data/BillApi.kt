package com.shopos.bills.data

import com.shopos.bills.BuildConfig
import com.shopos.bills.form.BillCreateRequest
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path

data class InitiateProofRequest(val client_upload_id: String, val content_type: String, val size_bytes: Long)
data class InitiatedProof(val id: String, val status: String, val upload_url: String?, val required_headers: Map<String, String>)
data class ProofInfo(val id: String, val status: String)
data class SavedBill(val id: String, val total_amount: String)

interface BillApi {
    @POST("attachments/proofs/initiate")
    suspend fun initiate(@Header("Authorization") auth: String, @Body request: InitiateProofRequest): InitiatedProof

    @POST("attachments/proofs/{id}/complete")
    suspend fun complete(@Header("Authorization") auth: String, @Path("id") id: String): ProofInfo

    @POST("bills")
    suspend fun create(@Header("Authorization") auth: String, @Body request: BillCreateRequest): SavedBill
}

class BillRepository(private val api: BillApi, private val tokenProvider: () -> String?, private val http: OkHttpClient = OkHttpClient()) {
    private fun auth() = "Bearer ${tokenProvider() ?: error("Sign in required")}"

    suspend fun upload(file: File, clientUploadId: String): String {
        val initiated = api.initiate(auth(), InitiateProofRequest(clientUploadId, "image/jpeg", file.length()))
        if (initiated.status == "ready") return initiated.id
        val url = initiated.upload_url ?: error("No upload URL returned")
        withContext(Dispatchers.IO) {
            val request = Request.Builder().url(url)
                .put(RequestBody.create(MediaType.parse("image/jpeg"), file))
                .header("Content-Type", initiated.required_headers["Content-Type"] ?: "image/jpeg")
                .build()
            http.newCall(request).execute().use { response ->
                if (!response.isSuccessful) error("Photo upload failed with ${response.code()}")
            }
        }
        val completed = api.complete(auth(), initiated.id)
        check(completed.status == "ready") { "Photo upload did not finish" }
        return completed.id
    }

    suspend fun create(request: BillCreateRequest): SavedBill = api.create(auth(), request)
}

fun billRepository(tokenProvider: () -> String?): BillRepository {
    val api = Retrofit.Builder().baseUrl(BuildConfig.API_BASE_URL)
        .addConverterFactory(GsonConverterFactory.create()).build().create(BillApi::class.java)
    return BillRepository(api, tokenProvider)
}
