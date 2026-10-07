from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PresignedUpload:
    url: str
    fields: dict[str, str]


class ObjectStorage(Protocol):
    def presign_upload(self, key: str, content_type: str, max_bytes: int) -> PresignedUpload: ...

    def presign_download(self, key: str, filename: str) -> str: ...

    def size(self, key: str) -> int | None:
        """Object size in bytes, or None when the object does not exist."""

    def read(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class S3Storage:
    def __init__(
        self,
        bucket: str,
        region: str,
        ttl_seconds: int,
        endpoint_url: str | None = None,
        public_endpoint_url: str | None = None,
    ):
        import boto3
        from botocore.config import Config

        def client(endpoint: str | None):
            return boto3.client(
                "s3",
                region_name=region,
                endpoint_url=endpoint,
                config=Config(signature_version="s3v4"),
            )

        self._bucket = bucket
        self._ttl = ttl_seconds
        self._client = client(endpoint_url)
        # Presigned URLs are opened by the browser. With MinIO in docker-compose
        # the browser reaches storage under a different host name than the API does.
        self._presign_client = client(public_endpoint_url or endpoint_url)

    def presign_upload(self, key: str, content_type: str, max_bytes: int) -> PresignedUpload:
        # A presigned POST (unlike PUT) lets S3 itself enforce the size limit.
        post = self._presign_client.generate_presigned_post(
            self._bucket,
            key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, max_bytes],
            ],
            ExpiresIn=self._ttl,
        )
        return PresignedUpload(url=post["url"], fields=post["fields"])

    def presign_download(self, key: str, filename: str) -> str:
        safe_name = filename.replace('"', "")
        return self._presign_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{safe_name}"',
            },
            ExpiresIn=self._ttl,
        )

    def size(self, key: str) -> int | None:
        from botocore.exceptions import ClientError

        try:
            return self._client.head_object(Bucket=self._bucket, Key=key)["ContentLength"]
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return None
            raise

    def read(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)
