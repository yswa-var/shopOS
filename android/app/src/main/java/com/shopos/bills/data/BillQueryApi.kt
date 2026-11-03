package com.shopos.bills.data

import com.shopos.bills.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.Path
import retrofit2.http.Query

data class BillSearchFilters(
    val vendor: String = "",
    val item: String = "",
    val employee: String = "",
    val dateFrom: String = "",
    val dateTo: String = "",
    val amountMin: String = "",
    val amountMax: String = "",
)

data class BillSearchRow(
    val id: String,
    val vendor_name: String,
    val bill_date: String,
    val total_amount: String,
    val employee_name: String,
    val item_names: List<String>,
)

data class BillSearchPage(val rows: List<BillSearchRow>, val has_more: Boolean)
data class BillDetailLine(val item_id: String, val item_name: String, val quantity: String, val price_basis: String, val unit_rate: String, val line_amount: String)
data class BillDetail(
    val id: String,
    val vendor_name: String,
    val employee_name: String,
    val bill_date: String,
    val proof_attachment_id: String,
    val items: List<BillDetailLine>,
    val subtotal: String,
    val tax_amount: String,
    val charges_amount: String,
    val total_amount: String,
    val created_at: String,
)
data class ProofDownload(val download_url: String)

interface BillQueryApi {
    @GET("bills")
    suspend fun search(
        @Header("Authorization") auth: String,
        @Query("vendor") vendor: String,
        @Query("item") item: String,
        @Query("employee") employee: String,
        @Query("date_from") dateFrom: String?,
        @Query("date_to") dateTo: String?,
        @Query("amount_min") amountMin: String?,
        @Query("amount_max") amountMax: String?,
        @Query("limit") limit: Int,
        @Query("offset") offset: Int,
    ): BillSearchPage

    @GET("bills/{id}")
    suspend fun detail(@Header("Authorization") auth: String, @Path("id") id: String): BillDetail

    @GET("attachments/proofs/{id}/download")
    suspend fun proof(@Header("Authorization") auth: String, @Path("id") id: String): ProofDownload
}

class BillQueryRepository(private val api: BillQueryApi, private val tokenProvider: () -> String?, private val http: OkHttpClient = OkHttpClient()) {
    private fun auth() = "Bearer ${tokenProvider() ?: error("Sign in required")}"
    private fun String.optional() = takeIf { it.isNotBlank() }

    suspend fun search(filters: BillSearchFilters, offset: Int): BillSearchPage = api.search(
        auth(), filters.vendor, filters.item, filters.employee,
        filters.dateFrom.optional(), filters.dateTo.optional(), filters.amountMin.optional(), filters.amountMax.optional(),
        30, offset,
    )

    suspend fun detail(id: String): BillDetail = api.detail(auth(), id)

    suspend fun proof(id: String): ByteArray {
        val signedUrl = api.proof(auth(), id).download_url
        return withContext(Dispatchers.IO) {
            http.newCall(Request.Builder().url(signedUrl).get().build()).execute().use { response ->
                if (!response.isSuccessful) error("Photo download failed with ${response.code()}")
                response.body()?.bytes() ?: error("Empty photo response")
            }
        }
    }
}

fun billQueryRepository(tokenProvider: () -> String?): BillQueryRepository = BillQueryRepository(
    Retrofit.Builder().baseUrl(BuildConfig.API_BASE_URL)
        .addConverterFactory(GsonConverterFactory.create()).build().create(BillQueryApi::class.java),
    tokenProvider,
)
