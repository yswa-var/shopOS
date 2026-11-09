import java.net.URI

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.devtools.ksp")
}

// The URL is public app configuration, not a secret. Read only this key from the
// repository's ignored .env so Android Studio builds use the same local setting.
val localApiUrl = providers.fileContents(rootProject.layout.projectDirectory.file("../.env"))
    .asText.orNull
    ?.lineSequence()
    ?.map { it.trim() }
    ?.firstOrNull { it.startsWith("SHOPOS_API_BASE_URL=") }
    ?.substringAfter('=')
    ?.trim()
    ?.removeSurrounding("\"")
    ?.removeSurrounding("'")
    ?.takeIf { it.isNotBlank() }

fun apiBaseUrl(defaultUrl: String, requireHttps: Boolean): String {
    val configured = providers.gradleProperty("shoposApiBaseUrl").orNull
        ?: providers.environmentVariable("SHOPOS_API_BASE_URL").orNull
        ?: localApiUrl
        ?: defaultUrl
    val uri = URI(configured.trim())
    require(uri.scheme in listOf("http", "https") && !uri.host.isNullOrBlank() && uri.rawQuery == null && uri.rawFragment == null) {
        "SHOPOS_API_BASE_URL must be an http(s) URL without a query or fragment"
    }
    // Android configures both variants even when only debug is being built.
    // Keep a local HTTP debug URL out of the release variant.
    if (requireHttps && uri.scheme != "https") return defaultUrl
    return uri.toASCIIString().trimEnd('/') + "/"
}

android {
    namespace = "com.shopos.bills"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.shopos.bills"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
    buildTypes {
        getByName("debug") {
            val apiUrl = apiBaseUrl("http://10.0.2.2:8000/", requireHttps = false)
            buildConfigField("String", "API_BASE_URL", "\"$apiUrl\"")
        }
        getByName("release") {
            val apiUrl = apiBaseUrl("https://example.invalid/", requireHttps = true)
            buildConfigField("String", "API_BASE_URL", "\"$apiUrl\"")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.compose.ui:ui:1.7.5")
    implementation("androidx.compose.material3:material3:1.3.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.4")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("androidx.room:room-runtime:2.8.5")
    implementation("androidx.room:room-ktx:2.8.5")
    ksp("androidx.room:room-compiler:2.8.5")
    implementation("androidx.camera:camera-camera2:1.6.2")
    implementation("androidx.camera:camera-lifecycle:1.6.2")
    implementation("androidx.camera:camera-view:1.6.2")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.4")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.9.0")
    testImplementation("junit:junit:4.13.2")
}

ksp {
    arg("room.schemaLocation", "$projectDir/schemas")
}
