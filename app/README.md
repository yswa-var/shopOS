# ShopOS Android app

Set the API address in `local.properties` at this directory's root. Android Studio
creates this file for the SDK path, and Git ignores it.

```properties
SHOPOS_API_BASE_URL=https://your-api.onrender.com/
```

Keep the trailing slash. The Android build embeds this value in `BuildConfig`.
For CI, set the `SHOPOS_API_BASE_URL` environment variable instead; it takes
precedence over `local.properties`.

Open this directory in Android Studio, sync Gradle, select your connected phone,
and press Run. The API must be reachable at `/health` before the catalogs load.
