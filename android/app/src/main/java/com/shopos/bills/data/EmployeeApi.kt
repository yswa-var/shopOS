package com.shopos.bills.data

import com.shopos.bills.BuildConfig
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path

data class PermissionInfo(val key: String, val label: String, val default: Boolean)
data class EmployeeRecord(val id: String, val username: String, val display_name: String, val is_active: Boolean, val permissions: List<String>)
data class EmployeeCreate(val username: String, val display_name: String, val password: String, val permissions: List<String>)
data class PermissionUpdate(val permissions: List<String>)
data class StatusUpdate(val is_active: Boolean)
data class ProfileUpdate(val display_name: String)
data class PasswordUpdate(val password: String)

interface EmployeeApi {
    @GET("employees/permissions")
    suspend fun permissions(@Header("Authorization") auth: String): List<PermissionInfo>

    @GET("employees")
    suspend fun employees(@Header("Authorization") auth: String): List<EmployeeRecord>

    @POST("employees")
    suspend fun create(@Header("Authorization") auth: String, @Body request: EmployeeCreate): EmployeeRecord

    @PUT("employees/{id}/permissions")
    suspend fun permissions(@Header("Authorization") auth: String, @Path("id") id: String, @Body request: PermissionUpdate): EmployeeRecord

    @PUT("employees/{id}/status")
    suspend fun status(@Header("Authorization") auth: String, @Path("id") id: String, @Body request: StatusUpdate): EmployeeRecord

    @PUT("employees/{id}/profile")
    suspend fun profile(@Header("Authorization") auth: String, @Path("id") id: String, @Body request: ProfileUpdate): EmployeeRecord

    @PUT("employees/{id}/password")
    suspend fun password(@Header("Authorization") auth: String, @Path("id") id: String, @Body request: PasswordUpdate)
}

class EmployeeRepository(private val api: EmployeeApi, private val tokenProvider: () -> String?) {
    private fun auth() = "Bearer ${tokenProvider() ?: error("Sign in required")}"
    suspend fun permissions() = api.permissions(auth())
    suspend fun employees() = api.employees(auth())
    suspend fun create(request: EmployeeCreate) = api.create(auth(), request)
    suspend fun permissions(id: String, values: List<String>) = api.permissions(auth(), id, PermissionUpdate(values))
    suspend fun status(id: String, active: Boolean) = api.status(auth(), id, StatusUpdate(active))
    suspend fun profile(id: String, name: String) = api.profile(auth(), id, ProfileUpdate(name))
    suspend fun password(id: String, password: String) = api.password(auth(), id, PasswordUpdate(password))
}

fun employeeRepository(tokenProvider: () -> String?): EmployeeRepository = EmployeeRepository(
    Retrofit.Builder().baseUrl(BuildConfig.API_BASE_URL)
        .addConverterFactory(GsonConverterFactory.create()).build().create(EmployeeApi::class.java),
    tokenProvider,
)
