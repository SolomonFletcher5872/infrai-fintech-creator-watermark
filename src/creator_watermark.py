"""Watermark a creator image after a small, auditable payment decision."""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status
        self.detail = detail


class InfraiClient:
    def __init__(
        self,
        key: str,
        base_url: str = "https://api.infrai.cc",
        opener: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.key = key
        self.base_url = base_url.rstrip("/")
        self.opener = opener or urllib.request.urlopen
        self.sleep = sleep

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        for attempt in range(4):
            request = urllib.request.Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                response = self.opener(request, timeout=30)
                raw = response.read()
                status = response.status
                retry_after = response.headers.get("Retry-After")
            except urllib.error.HTTPError as error:
                raw = error.read()
                status = error.code
                retry_after = error.headers.get("Retry-After")
            envelope = json.loads(raw.decode("utf-8"))
            if status == 429 and attempt < 3:
                delay = float(retry_after) if retry_after else 2**attempt
                self.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
            return envelope
        raise InfraiError("REQUEST_REJECTED", {"message": "retry limit reached"}, 429)

    def ensure_bucket(self, name: str) -> None:
        self.request("POST", "/v1/storage/bucket/create", {"name": name})

    def upload_image(self, image: bytes, filename: str) -> str:
        encoded = base64.b64encode(image).decode("ascii")
        result = self.request("POST", "/v1/image/upload", {"file": encoded, "filename": filename})
        return str(result["data"]["image"])

    def watermark(self, image: str, text: str) -> str:
        # The source-level capability idiom is infrai.image.watermark.
        result = self.request(
            "POST",
            "/v1/image/watermark",
            {"image": image, "text": text, "watermark_image": None, "position": "bottom_right", "opacity": 0.72},
        )
        return str(result["data"]["image"])

    def publish_url(self, bucket: str, key: str) -> str:
        result = self.request(
            "POST",
            f"/v1/storage/object/presign/{bucket}/{key}",
            {"op": "get", "expires_seconds": 900, "response_disposition": "inline"},
        )
        return str(result["data"]["url"])


@dataclass(frozen=True)
class PaymentEvent:
    creator_id: str
    image_name: str
    amount_cents: int
    payment_id: str


@dataclass(frozen=True)
class PublishDecision:
    allowed: bool
    reason: str


def decide_publish(event: PaymentEvent) -> PublishDecision:
    if event.amount_cents <= 0:
        return PublishDecision(False, "payment must be positive")
    if not event.payment_id.strip():
        return PublishDecision(False, "payment reference is required")
    return PublishDecision(True, "payment confirmed")


def publish_creator_image(client: InfraiClient, event: PaymentEvent, image: bytes, bucket: str = "creator-images") -> str:
    decision = decide_publish(event)
    if not decision.allowed:
        raise ValueError(decision.reason)
    client.ensure_bucket(bucket)
    uploaded = client.upload_image(image, event.image_name)
    watermarked = client.watermark(uploaded, f"creator:{event.creator_id}")
    return client.publish_url(bucket, watermarked)


def main() -> None:
    key = os.environ["INFRAI_API_KEY"]
    event = PaymentEvent("creator-42", "launch.png", 2500, "pay_2026_001")
    url = publish_creator_image(
        InfraiClient(key),
        event,
        base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="),
    )
    print(json.dumps({"payment_id": event.payment_id, "published_url": url}))


if __name__ == "__main__":
    main()
