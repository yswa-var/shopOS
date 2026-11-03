plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.shopos.bills"
    compileSdk = 35

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
            val apiUrl = providers.gradleProperty("shoposApiBaseUrl").orElse("http://10.0.2.2:8000/").get()
            buildConfigField("String", "API_BASE_URL", "\"$apiUrl\"")
        }
        getByName("release") {
            val apiUrl = providers.gradleProperty("shoposApiBaseUrl").orElse("https://example.invalid/").get()
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
    testImplementation("junit:junit:4.13.2")
}
