# Private proof-photo attachments

Q04 provides a two-step upload and signed download contract. The bucket must be private. PostgreSQL stores proof metadata and private object keys; API responses never expose the final object key. The backend uses S3-compatible calls, so local SeaweedFS and a hosted S3-compatible provider share one code path.

## API flow

All requests need an employee bearer token. Employees need `attachments:write` to initiate or complete their own uploads. Unlinked uploads require `attachments:read` and uploader ownership for inspection or download. Linked proofs follow `bills:read` and can be viewed by any employee allowed to read the bill. The owner may access any proof. See `docs/bill-query.md`.

1. `POST /attachments/proofs/initiate` with `client_upload_id` (UUID), `content_type` (`image/jpeg`, `image/png`, or `image/webp`), and `size_bytes` (1–15,000,000). Store the upload ID with the local draft.
2. The response gives an attachment `id`, a signed `upload_url`, `required_headers`, and a 300-second lifetime. Send the raw image bytes with HTTP `PUT` to that URL, including the exact `Content-Type` header. This request goes to object storage, not the API.
3. `POST /attachments/proofs/{id}/complete`. The server checks object size, content type, and image signature, copies the temporary object to a private final key, checks the copy, and marks the attachment `ready`. Q05 must confirm that a ready attachment belongs to the bill creator before linking it to a saved bill.
4. `GET /attachments/proofs/{id}` returns status and metadata. `GET /attachments/proofs/{id}/download` returns a 300-second signed GET URL only when ready and authorized.

Retry initiation with the same `client_upload_id` and identical metadata to receive the same attachment ID and a fresh signed PUT URL. A ready upload returns `upload_url: null`. Reusing the ID with different metadata returns 409. Completion before upload or with mismatched size/type returns 409; invalid image signatures return 422; storage outage returns 503. These leave the attachment pending so the client can reupload and retry. Completion of an already ready attachment is idempotent. The final key is never exposed through a signed PUT, so a late retry cannot change a completed proof.

The current check recognizes JPEG, PNG, and WebP signatures and does not fully decode the image. Q05 added CameraX capture, local draft recovery, and the bill transaction. Q06 added linked-bill proof access. Q08 added a bounded cleanup command: `uv run python -m shopos.proof_cleanup --limit 100`. It deletes pending uploads older than seven days, removes their temporary and unlinked final objects, and retries failed temporary-object deletion for ready proofs. Ready proof objects are retained. Schedule the command in production; it is not run by the API process.

## Local storage

Copy `.env.example` to ignored `.env`, replace `S3_SECRET_ACCESS_KEY`, and run `make install` then `make storage-up`. This writes an ignored `.local/seaweedfs-s3.json`, starts the loopback-bound SeaweedFS S3 service on port 9000, and creates a private bucket. The Android emulator uses `S3_PUBLIC_ENDPOINT_URL=http://10.0.2.2:9000`; for a host-side integration check, set it to `http://127.0.0.1:9000`. A physical device needs a reachable HTTPS S3 endpoint or a secured local network setup. Use `make storage-down` to stop the service without deleting its volume.

For a live synthetic upload/download check, set the usual database and S3 environment variables plus `SHOPOS_TEST_S3=1`, then run `uv run pytest backend/tests/test_storage_live.py`. The test uploads one tiny synthetic PNG through the signed URL, verifies the private direct URL is denied, and deletes its objects afterward.

## Render or another provider

Create a private S3-compatible bucket outside Render, then provide `S3_BUCKET`, `S3_REGION`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, and `S3_SECRET_ACCESS_KEY` in the Render service environment. `S3_PUBLIC_ENDPOINT_URL` is optional when the same HTTPS endpoint is reachable by both API and Android clients. Use HTTPS for real devices. The application can later use an IAM credential provider by leaving both explicit key variables unset. Never make the bucket public or commit credentials.

[Boto3 signed URL reference](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/generate_presigned_url.html) · [Render Blueprint secret variables](https://render.com/docs/blueprint-spec)
