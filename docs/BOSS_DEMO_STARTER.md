# ShopOS V1 Demo Brief

**Audience:** Shop owners and managers  
**Purpose:** Review a working prototype for recording and finding supplier purchase bills  
**Demo status:** Local test build; production deployment has not been completed

## What ShopOS solves

Shop staff need to record a purchase bill while serving customers and find it later without searching through paper or chat photos. ShopOS provides one shared, searchable record with the bill's items, amounts, employee, and proof photo. The owner controls who can use each feature.

## What to show in the demo

Use made-up vendors, items, amounts, and photos. Allow about 10 minutes.

| Step | Show | Point to make |
|---|---|---|
| 1 | Sign in with an employee account | Each employee has an individual login. |
| 2 | Start a purchase bill and select or create a vendor | Staff can add a missing vendor without leaving the bill. |
| 3 | Add two items, quantities, prices, tax or charges | One bill supports multiple items and shows the payable total. |
| 4 | Capture or attach a proof photo, then save | The proof is required; retrying a save is designed to avoid duplicates. |
| 5 | Search by vendor, item, date, amount, or employee; open the bill | Staff can retrieve the details and authorized proof photo. |
| 6 | Sign in as owner and open employee management | The owner can create or deactivate employees and change permissions. |

If the live camera, network, or storage connection is unavailable, show the completed screens and explain which step could not be demonstrated. Do not enter real shop data for this first review.

## Questions for the review

1. Can an employee enter a typical bill quickly enough during a busy counter shift?
2. Are the vendor and item names, price fields, tax, and charges presented in the way staff expect?
3. Can staff find an older bill using the details they normally remember?
4. Which employees should be allowed to create bills, view all bills, and manage catalogs?
5. What changes are required before a small in-shop pilot?

## Current readiness and limits

The backend, database migrations, Android debug build, and automated checks have passed. A local API and private photo storage were previously tested, including signed upload and viewing. A complete interactive run on an Android device still needs to be done with the API and storage running. The current release APK is unsigned, and Render deployment has not been performed.

V1 covers purchase bills only. Sales, inventory balances, accounting, OCR, analytics, and offline bill submission are outside this version. PostgreSQL stores the shared records; an unfinished bill can be kept as a local device draft.

## Demo setup reminder

From the project directory, start Docker, create `.env` as described in the README, then run `make db-up`, `make migrate`, and `make storage-up`. Run `make bootstrap-owner` once to create the first owner with a private password, then `make api`. These Make targets load `.env` directly. For an Android emulator, the debug build points to the host API at `10.0.2.2:8000`. Use the debug APK at `android/app/build/outputs/apk/debug/app-debug.apk`.

**Suggested outcome:** Agree on a short staff trial using synthetic bills first, record time to enter and retrieve a bill, and collect changes before production deployment.
