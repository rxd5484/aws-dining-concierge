from __future__ import annotations

import json
import os
import time
import uuid
from decimal import Decimal
from typing import Any

import boto3

from common.validation import validate_request

DDB_TABLE = os.environ["REQUESTS_TABLE"]
EVENT_BUS = os.environ["EVENT_BUS_NAME"]

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(DDB_TABLE)
events = boto3.client("events")


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "content-type",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(body),
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _handle_post(event: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(event.get("body") or "{}")
        request_data = validate_request(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        return _response(400, {"error": str(exc)})

    request_id = str(uuid.uuid4())
    now = int(time.time())
    item = {
        "request_id": request_id,
        "status": "QUEUED",
        "created_at": now,
        "ttl": now + (30 * 24 * 60 * 60),
        **request_data,
    }
    table.put_item(Item=item)

    put_result = events.put_events(
        Entries=[
            {
                "Source": "dining.concierge",
                "DetailType": "DiningRequestSubmitted",
                "Detail": json.dumps({"request_id": request_id, **request_data}),
                "EventBusName": EVENT_BUS,
            }
        ]
    )
    if put_result.get("FailedEntryCount", 0):
        table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "FAILED_TO_QUEUE"},
        )
        return _response(500, {"error": "Could not queue request. Please retry."})

    return _response(
        202,
        {
            "request_id": request_id,
            "status": "QUEUED",
            "message": "Request accepted. Recommendations are being prepared.",
        },
    )


def _handle_get(event: dict[str, Any]) -> dict[str, Any]:
    request_id = (event.get("pathParameters") or {}).get("request_id")
    if not request_id:
        return _response(400, {"error": "request_id is required"})

    result = table.get_item(Key={"request_id": request_id})
    item = result.get("Item")
    if not item:
        return _response(404, {"error": "Request not found"})

    # Keep user-facing payload compact.
    public_fields = {
        key: item.get(key)
        for key in [
            "request_id", "status", "location", "cuisine", "date", "time",
            "party_size", "recommendations", "email_sent", "error",
        ]
        if key in item
    }
    return _response(200, _json_safe(public_fields))


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or ""
    ).upper()

    if method == "OPTIONS":
        return _response(204, {})
    if method == "POST":
        return _handle_post(event)
    if method == "GET":
        return _handle_get(event)
    return _response(405, {"error": "Method not allowed"})
