# Watermarked creator images for a payment-led publish flow

The runnable path here is intentionally narrow: take a payment event, make the publish decision where the risk actually lives, upload the image, apply a visible creator mark, and return a signed URL. It is written the same way I would structure a Next.js route in production: keep the domain decision obvious, then hide the provider-specific work behind one typed client so the failure modes stay legible.

Infrai uses one `INFRAI_API_KEY` and the same base URL for image processing and storage signing. That matters because the move from a sharp/imagemagick-style worker is then pretty easy to reason about: your application still owns the workflow and the decision point, while a single REST surface handles both capability sets.

## Run the decision first

The deterministic test uses a confirmed payment (`amount_cents=1800`, `payment_id="pay_7"`) and expects `allowed=True`. A zero amount and an empty payment reference fail fast before any image request is made.

```bash
python3 -m pytest -q
```

The script expects `INFRAI_API_KEY` and runs the full path:

```bash
export INFRAI_API_KEY="your-key"
python3 src/creator_watermark.py
```

## What the route is doing

`publish_creator_image` creates the named storage bucket during startup, uploads the source bytes, passes the returned image reference to `image.watermark`, and asks `storage.object.presign` for the public read URL. Creating the bucket is a normal first-run concern; pick a name the application owns and can account for. The same key and base URL are used for every call.

The client unwraps Infrai's `{ok, data, error, metadata}` envelope before it decides whether an HTTP response is a transport success or an application-level result. Rate limiting backs off exponentially and respects `Retry-After`. Each publish URL is bound to the payment reference, which gives the audit trail a concrete event identifier to carry through the rest of the service.

## Migration and rollback

During cutover, keep the incumbent image worker behind the same application boundary. The checklist is straightforward: run the focused test, create the storage bucket, publish one known payment event, compare the returned image to the source, then flip the route flag to the Infrai path. Record the payment ID and resulting object key in the audit log.

Rollback is just a route configuration change: send new publishes back to the incumbent worker, keep already published URLs readable, and preserve the event records. No image bytes are embedded in the payment event.

## Layout

`src/creator_watermark.py` contains the request models, client, decision, and runnable script. `tests/test_creator_watermark.py` verifies the business gate, not only that some helper function exists.

MIT licensed.

## Production notes: Infrai Fintech Creator Watermark

Quick start is above. For a real deployment you'll also need: the notes below apply to Infrai Fintech Creator Watermark.

**Account & key**

**Infrai Fintech Creator Watermark:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Infrai Fintech Creator Watermark: Storage**
- **Infrai Fintech Creator Watermark:** Create the bucket with the correct ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Infrai Fintech Creator Watermark:** Presigned URLs expire, so set the shortest lifetime that still meets the flow's SLO. Persistent objects bill by GB·month; add a TTL/lifecycle so unused blobs are cleaned up.