package com.shopos.bills.catalog

import com.shopos.bills.BuildConfig
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

data class CatalogEntry(val id: String, val name: String, val aliases: List<String>)
data class CatalogCreateRequest(val name: String, val aliases: List<String>)
data class AliasCreateRequest(val alias: String)

interface CatalogApi {
    @GET("catalog/vendors")
    suspend fun vendors(@Header("Authorization") authorization: String, @Query("q") query: String): List<CatalogEntry>

    @GET("catalog/items")
    suspend fun items(@Header("Authorization") authorization: String, @Query("q") query: String): List<CatalogEntry>

    @POST("catalog/vendors")
    suspend fun createVendor(@Header("Authorization") authorization: String, @Body request: CatalogCreateRequest): CatalogEntry

    @POST("catalog/items")
    suspend fun createItem(@Header("Authorization") authorization: String, @Body request: CatalogCreateRequest): CatalogEntry

    @POST("catalog/vendors/{id}/aliases")
    suspend fun addVendorAlias(@Header("Authorization") authorization: String, @Path("id") id: String, @Body request: AliasCreateRequest): CatalogEntry

    @POST("catalog/items/{id}/aliases")
    suspend fun addItemAlias(@Header("Authorization") authorization: String, @Path("id") id: String, @Body request: AliasCreateRequest): CatalogEntry
}

enum class CatalogKind { VENDOR, ITEM }

class CatalogRepository(private val api: CatalogApi, private val tokenProvider: () -> String?) {
    private fun authorization(): String = "Bearer ${tokenProvider() ?: error("Sign in required")}"

    suspend fun search(kind: CatalogKind, query: String): List<CatalogEntry> = when (kind) {
        CatalogKind.VENDOR -> api.vendors(authorization(), query)
        CatalogKind.ITEM -> api.items(authorization(), query)
    }

    suspend fun create(kind: CatalogKind, name: String, aliases: List<String>): CatalogEntry {
        val request = CatalogCreateRequest(name, aliases)
        return when (kind) {
            CatalogKind.VENDOR -> api.createVendor(authorization(), request)
            CatalogKind.ITEM -> api.createItem(authorization(), request)
        }
    }

    suspend fun addAlias(kind: CatalogKind, id: String, alias: String): CatalogEntry {
        val request = AliasCreateRequest(alias)
        return when (kind) {
            CatalogKind.VENDOR -> api.addVendorAlias(authorization(), id, request)
            CatalogKind.ITEM -> api.addItemAlias(authorization(), id, request)
        }
    }
}

fun catalogRepository(tokenProvider: () -> String?): CatalogRepository = CatalogRepository(
    Retrofit.Builder()
        .baseUrl(BuildConfig.API_BASE_URL)
        .addConverterFactory(GsonConverterFactory.create())
        .build()
        .create(CatalogApi::class.java),
    tokenProvider,
)
