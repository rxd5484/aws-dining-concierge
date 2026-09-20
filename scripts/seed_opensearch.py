"""Seed an existing AWS OpenSearch domain with demo restaurant documents.

Usage:
  export OPENSEARCH_ENDPOINT=https://search-your-domain....amazonaws.com
  export AWS_REGION=us-east-1
  python scripts/seed_opensearch.py

The current AWS CLI/profile credentials must have es:ESHttp* access to the domain.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
from common.sample_restaurants import SAMPLE_RESTAURANTS  # noqa: E402

endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "").strip()
region = os.environ.get("AWS_REGION", "us-east-1")
index = os.environ.get("OPENSEARCH_INDEX", "restaurants")

if not endpoint:
    raise SystemExit("Set OPENSEARCH_ENDPOINT first.")

credentials = boto3.Session().get_credentials()
auth = AWSV4SignerAuth(credentials, region, "es")
host = endpoint.replace("https://", "").replace("http://", "").rstrip("/")
client = OpenSearch(
    hosts=[{"host": host, "port": 443}],
    http_auth=auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
)

if not client.indices.exists(index=index):
    client.indices.create(
        index=index,
        body={
            "mappings": {
                "properties": {
                    "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                    "cuisine": {"type": "keyword"},
                    "location": {"type": "keyword"},
                    "rating": {"type": "float"},
                    "address": {"type": "text"},
                }
            }
        },
    )

for i, restaurant in enumerate(SAMPLE_RESTAURANTS, start=1):
    client.index(index=index, id=str(i), body=restaurant, refresh=True)

print(json.dumps({"indexed": len(SAMPLE_RESTAURANTS), "index": index}, indent=2))
