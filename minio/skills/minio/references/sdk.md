# SDK / S3 API access: Python, Go, JavaScript

MinIO speaks the S3 API, so any S3 SDK works against it. Two Python paths
exist: the official `minio` SDK (MinIO-native, simpler for MinIO-specific
features) and `boto3` (AWS's SDK, useful when code must also target real
AWS S3). Pick based on what the codebase already uses; don't introduce a
second S3 client library into a project that already has one.

**Before writing SDK code, check the installed package version** (`pip show minio`,
`npm ls minio`, `go list -m github.com/minio/minio-go/v7`) — method signatures
below are the stable, long-standing API surface, but always verify against
the version actually installed rather than assuming.

## Python: `minio` (official MinIO SDK)

```python
from minio import Minio
from minio.error import S3Error

client = Minio(
    "minio.example.com:9000",   # host:port, no scheme
    access_key="ACCESSKEY",
    secret_key="SECRETKEY",
    secure=True,                 # False only for plain-HTTP dev endpoints
)

# Buckets
client.make_bucket("mybucket")
if not client.bucket_exists("mybucket"):
    client.make_bucket("mybucket")
for obj in client.list_objects("mybucket", prefix="logs/", recursive=True):
    print(obj.object_name, obj.size)

# Objects
client.fput_object("mybucket", "path/in/bucket.txt", "/local/file.txt")
client.fget_object("mybucket", "path/in/bucket.txt", "/local/dest.txt")
client.remove_object("mybucket", "path/in/bucket.txt")

# Presigned URLs (default/max validity is 7 days, matching mc share)
from datetime import timedelta
url = client.presigned_get_object("mybucket", "obj.txt", expires=timedelta(hours=1))
upload_url = client.presigned_put_object("mybucket", "obj.txt", expires=timedelta(minutes=10))

try:
    client.stat_object("mybucket", "obj.txt")
except S3Error as exc:
    print(exc.code, exc.message)   # e.g. NoSuchKey
```
Credentials: never hardcode `access_key`/`secret_key` in source — read from
environment variables or a secrets manager and confirm with the user where
theirs should come from if unstated.

## Python: `boto3` against MinIO

The only MinIO-specific bits are `endpoint_url`, forcing `s3v4` signing, and
(usually) path-style addressing:

```python
import boto3
from botocore.client import Config

s3 = boto3.client(
    "s3",
    endpoint_url="https://minio.example.com:9000",
    aws_access_key_id="ACCESSKEY",
    aws_secret_access_key="SECRETKEY",
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    region_name="us-east-1",   # MinIO ignores the value but boto3 requires one
)

s3.create_bucket(Bucket="mybucket")
s3.upload_file("/local/file.txt", "mybucket", "path/in/bucket.txt")
s3.download_file("mybucket", "path/in/bucket.txt", "/local/dest.txt")
for page in s3.get_paginator("list_objects_v2").paginate(Bucket="mybucket", Prefix="logs/"):
    for obj in page.get("Contents", []):
        print(obj["Key"], obj["Size"])

url = s3.generate_presigned_url(
    "get_object", Params={"Bucket": "mybucket", "Key": "obj.txt"}, ExpiresIn=3600
)
```
`addressing_style: "path"` matches `mc alias set ... --path on`; if the
MinIO deployment uses DNS-style buckets (`--path off`), use
`"virtual"` instead — ask if unclear rather than guessing per-deployment.

## Go: `minio-go/v7`

```go
import (
    "context"
    "github.com/minio/minio-go/v7"
    "github.com/minio/minio-go/v7/pkg/credentials"
)

client, err := minio.New("minio.example.com:9000", &minio.Options{
    Creds:  credentials.NewStaticV4("ACCESSKEY", "SECRETKEY", ""),
    Secure: true,
})

ctx := context.Background()
_, err = client.FPutObject(ctx, "mybucket", "path/in/bucket.txt", "/local/file.txt", minio.PutObjectOptions{})
obj, err := client.GetObject(ctx, "mybucket", "path/in/bucket.txt", minio.GetObjectOptions{})

url, err := client.PresignedGetObject(ctx, "mybucket", "obj.txt", time.Hour, nil)
```
For manual multipart/segmented control (rare — the high-level API already
handles multipart internally above MinIO's threshold), use
`client.Core()` (`NewMultipartUpload`/`PutObjectPart`/`CompleteMultipartUpload`).

## JavaScript/TypeScript: `minio` npm package

```javascript
const { Client } = require('minio')

const client = new Client({
  endPoint: 'minio.example.com',
  port: 9000,
  useSSL: true,
  accessKey: 'ACCESSKEY',
  secretKey: 'SECRETKEY',
})

await client.fPutObject('mybucket', 'path/in/bucket.txt', '/local/file.txt')
await client.fGetObject('mybucket', 'path/in/bucket.txt', '/local/dest.txt')

const stream = client.listObjectsV2('mybucket', 'logs/', true)
stream.on('data', (obj) => console.log(obj.name, obj.size))

const url = await client.presignedGetObject('mybucket', 'obj.txt', 3600)
```

## Cross-language topics

- **Multipart uploads**: all SDKs above switch to multipart automatically past
  a size threshold (commonly ~64MiB–128MiB depending on SDK/version) — don't
  hand-roll multipart unless you need explicit control over part size/count
  or parallelism beyond what the high-level `put`/`upload` call gives you.
- **Presigned URLs**: 7 days is the S3/MinIO protocol maximum validity for a
  presigned URL, matching `mc share download`'s default. Requesting a longer
  expiry will fail or be silently clamped depending on SDK — don't promise a
  user a longer-lived link than that.
- **STS temporary credentials**: `AssumeRole` (for a MinIO/IAM user) and
  `AssumeRoleWithWebIdentity` (for federated/OIDC identities) return
  short-lived access/secret/session-token triples via the STS API — every
  SDK above has an STS client or a `credentials` provider for this
  (`minio-py`: `minio.credentials.AssumeRoleProvider`; boto3: `sts` client
  pointed at the same `endpoint_url`; minio-go: `credentials.NewSTSAssumeRole`).
  Prefer STS-issued temporary credentials over long-lived access keys for
  anything that isn't a human operator, when the deployment has IAM/OIDC set
  up for it.
- **Credential precedence**: explicit constructor args > environment
  variables (`MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` server-side;
  `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` for boto3-style clients) >
  a config/credentials file. Never hardcode credentials in source under any
  circumstance; if the user's existing code does, flag it rather than
  quietly perpetuating the pattern.
