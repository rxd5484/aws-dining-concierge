from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Any

import boto3

from common.sample_restaurants import SAMPLE_RESTAURANTS

REQUESTS_TABLE = os.environ["REQUESTS_TABLE"]
SES_FROM_EMAIL = os.environ.get("SES_FROM_EMAIL", "").strip()
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "").strip()
OPENSEARCH_INDEX = os.environ.get("OPENSEARCH_INDEX", "restaurants")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(REQUESTS_TABLE)
ses = boto3.client("ses")


def _search_sample(cuisine: str, location: str, limit: int = 3) -> list[dict[str, Any]]:
    exact = [
        r for r in SAMPLE_RESTAURANTS
        if r["cuisine"].lower() == cuisine.lower()
        and (
            location.lower() == "new york city"
            or r["location"].lower() == location.lower()
        )
    ]
    if len(exact) < limit:
        exact += [
            r for r in SAMPLE_RESTAURANTS
            if r["cuisine"].lower() == cuisine.lower() and r not in exact
        ]
    return sorted(exact, key=lambda r: r["rating"], reverse=True)[:limit]


def _search_opensearch(cuisine: str, location: str, limit: int = 3) -> list[dict[str, Any]]:
    if not OPENSEARCH_ENDPOINT:
        return _search_sample(cuisine, location, limit)

    try:
        from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

        credentials = boto3.Session().get_credentials()
        auth = AWSV4SignerAuth(credentials, AWS_REGION, "es")
        host = OPENSEARCH_ENDPOINT.replace("https://", "").replace("http://", "").rstrip("/")
        client = OpenSearch(
            hosts=[{"host": host, "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
        )

        filters: list[dict[str, Any]] = [
            {"term": {"cuisine": cuisine}},
        ]
        if location.lower() != "new york city":
            filters.append({"term": {"location": location}})

        result = client.search(
            index=OPENSEARCH_INDEX,
            body={
                "size": limit,
                "query": {"bool": {"filter": filters}},
                "sort": [{"rating": {"order": "desc"}}],
            },
        )
        hits = [hit["_source"] for hit in result.get("hits", {}).get("hits", [])]
        return hits or _search_sample(cuisine, location, limit)
    except Exception as exc:  # fall back so the demo stays resilient
        print(f"OpenSearch unavailable, using bundled sample data: {exc}")
        return _search_sample(cuisine, location, limit)


def _to_dynamodb(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [_to_dynamodb(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_dynamodb(v) for k, v in value.items()}
    return value


def _format_email(detail: dict[str, Any], recommendations: list[dict[str, Any]]) -> str:
    header = (
        f"Dining recommendations for {detail['cuisine']} food in {detail['location']}\n"
        f"Date: {detail['date']} at {detail['time']} | Party of {detail['party_size']}\n\n"
    )
    if not recommendations:
        return header + "We could not find a matching restaurant. Try another cuisine or location."

    lines = []
    for idx, restaurant in enumerate(recommendations, start=1):
        lines.append(
            f"{idx}. {restaurant['name']} — {restaurant.get('rating', 'N/A')}/5\n"
            f"   {restaurant.get('address', restaurant.get('location', 'New York City'))}"
        )
    return header + "\n\n".join(lines)


def _send_email(to_email: str, detail: dict[str, Any], recommendations: list[dict[str, Any]]) -> bool:
    if not SES_FROM_EMAIL:
        print("SES_FROM_EMAIL is empty; skipping email delivery.")
        return False

    ses.send_email(
        Source=SES_FROM_EMAIL,
        Destination={"ToAddresses": [to_email]},
        Message={
            "Subject": {"Data": "Your Dining Concierge Recommendations"},
            "Body": {"Text": {"Data": _format_email(detail, recommendations)}},
        },
    )
    return True


def _process(detail: dict[str, Any]) -> None:
    request_id = detail["request_id"]
    table.update_item(
        Key={"request_id": request_id},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "PROCESSING"},
    )

    try:
        recommendations = _search_opensearch(detail["cuisine"], detail["location"], 3)
        email_sent = _send_email(detail["email"], detail, recommendations)

        table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #s = :s, recommendations = :r, email_sent = :e",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "COMPLETED",
                ":r": _to_dynamodb(recommendations),
                ":e": email_sent,
            },
        )
    except Exception as exc:
        print(f"Failed request {request_id}: {exc}")
        table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #s = :s, #err = :e",
            ExpressionAttributeNames={"#s": "status", "#err": "error"},
            ExpressionAttributeValues={":s": "FAILED", ":e": str(exc)[:500]},
        )
        raise


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    for record in event.get("Records", []):
        body = json.loads(record["body"])
        detail = body.get("detail", body)
        _process(detail)
    return {"processed": len(event.get("Records", []))}
