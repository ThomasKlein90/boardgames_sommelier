import argparse
import json
import sys
from typing import Iterable, List

import boto3

DEFAULT_BRONZE_BUCKET = "boardgames-sommelier-bronze-dev-021406833830"
DEFAULT_SILVER_BUCKET = "boardgames-sommelier-silver-dev-021406833830"
DEFAULT_REGION = "ap-southeast-2"
DEFAULT_LAMBDA_ARN = (
    "arn:aws:lambda:ap-southeast-2:021406833830:function:"
    "boardgames_sommelier_clean_bgg_data"
)

BRONZE_PREFIX = "bgg/raw_games/"
SILVER_DIM_GAME_PREFIX = "bgg/dim_game/"


def iter_s3_keys(s3_client, bucket: str, prefix: str) -> Iterable[str]:
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            yield obj["Key"]


def chunked(items: List[str], size: int) -> Iterable[List[str]]:
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def delete_prefix(s3_client, bucket: str, prefix: str) -> int:
    deleted = 0
    batch = []

    for key in iter_s3_keys(s3_client, bucket, prefix):
        batch.append({"Key": key})
        if len(batch) == 1000:
            s3_client.delete_objects(Bucket=bucket, Delete={"Objects": batch})
            deleted += len(batch)
            batch = []

    if batch:
        s3_client.delete_objects(Bucket=bucket, Delete={"Objects": batch})
        deleted += len(batch)

    return deleted


def build_s3_event_records(bucket: str, keys: List[str]) -> dict:
    return {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": bucket},
                    "object": {"key": key},
                }
            }
            for key in keys
        ]
    }


def invoke_lambda_batches(lambda_client, lambda_arn: str, bucket: str, keys: List[str], batch_size: int) -> int:
    invoked = 0
    for batch in chunked(keys, batch_size):
        payload = build_s3_event_records(bucket, batch)
        lambda_client.invoke(
            FunctionName=lambda_arn,
            InvocationType="Event",
            Payload=json.dumps(payload).encode("utf-8"),
        )
        invoked += len(batch)
    return invoked


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill silver dim_game from bronze raw_games.")
    parser.add_argument("--bronze-bucket", default=DEFAULT_BRONZE_BUCKET)
    parser.add_argument("--silver-bucket", default=DEFAULT_SILVER_BUCKET)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--lambda-arn", default=DEFAULT_LAMBDA_ARN)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--purge-silver", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    session = boto3.Session(region_name=args.region)
    s3_client = session.client("s3")
    lambda_client = session.client("lambda")

    if args.purge_silver:
        if not args.confirm:
            print("Refusing to purge silver without --confirm.")
            return 2
        print(f"Purging s3://{args.silver_bucket}/{SILVER_DIM_GAME_PREFIX}")
        deleted = delete_prefix(s3_client, args.silver_bucket, SILVER_DIM_GAME_PREFIX)
        print(f"Deleted {deleted} objects from silver dim_game prefix.")

    print(f"Listing bronze objects under s3://{args.bronze_bucket}/{BRONZE_PREFIX}")
    keys = list(iter_s3_keys(s3_client, args.bronze_bucket, BRONZE_PREFIX))
    if not keys:
        print("No bronze objects found. Nothing to backfill.")
        return 0

    print(f"Invoking Lambda in batches of {args.batch_size} for {len(keys)} objects...")
    invoked = invoke_lambda_batches(lambda_client, args.lambda_arn, args.bronze_bucket, keys, args.batch_size)
    print(f"Submitted {invoked} objects to Lambda.")
    print("Note: invocations are async; monitor CloudWatch logs for completion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
