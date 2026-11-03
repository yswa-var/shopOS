package com.shopos.bills.auth

import com.shopos.bills.BuildConfig
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST

data class LoginRequest(val username: String, val password: String)
data class TokenResponse(val access_token: String, val user: UserResponse)
data class UserResponse(val username: String, val display_name: String, val role: String)

interface AuthApi {
    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): TokenResponse

    @GET("auth/me")
    suspend fun me(@Header("Authorization") authorization: String): UserResponse

    @POST("auth/logout")
    suspend fun logout(@Header("Authorization") authorization: String)
}

class AuthRepository(private val api: AuthApi) {
    suspend fun login(username: String, password: String): Pair<String, UserResponse> {
        val response = api.login(LoginRequest(username, password))
        return response.access_token to response.user
    }

    suspend fun logout(token: String) {
        api.logout("Bearer $token")
    }
}

fun authRepository(): AuthRepository = AuthRepository(
    Retrofit.Builder()
        .baseUrl(BuildConfig.API_BASE_URL)
        .addConverterFactory(GsonConverterFactory.create())
        .build()
        .create(AuthApi::class.java)
)
