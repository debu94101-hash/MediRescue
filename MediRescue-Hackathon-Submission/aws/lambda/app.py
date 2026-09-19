import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3  # type: ignore

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])
sns = boto3.client("sns")
TOPIC_ARN = os.environ["TOPIC_ARN"]

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "content-type,authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Content-Type": "application/json",
}

def response(status_code, body):
    return {"statusCode": status_code, "headers": CORS_HEADERS, "body": json.dumps(body, default=str)}

def lambda_handler(event, context):
    try:
        if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
            return response(204, {})

        body = json.loads(event.get("body") or "{}")
        lat = body.get("latitude")
        lon = body.get("longitude")
        if lat is not None and not (-90 <= float(lat) <= 90):
            return response(400, {"error": "Invalid latitude"})
        if lon is not None and not (-180 <= float(lon) <= 180):
            return response(400, {"error": "Invalid longitude"})

        item = {
            "emergency_id": str(uuid.uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": body.get("status", "active"),
            "severity": body.get("severity", "CRITICAL"),
            "notification_type": body.get("notification_type", "NEW_CRITICAL_EMERGENCY"),
        }

        allowed_fields = [
            "latitude", "longitude", "accuracy", "priority",
            "patient_name", "patient_phone", "notes",
            "priority_hospital_id", "priority_hospital_name",
            "priority_hospital_distance_km", "hospital_count",
            "event_type", "source", "message",
        ]

        for key in allowed_fields:
            if body.get(key) is not None:
                value = body[key]
                if key in ["latitude", "longitude", "accuracy", "priority_hospital_distance_km"]:
                    value = Decimal(str(value))
                item[key] = value

        table.put_item(Item=item)

        sns.publish(
            TopicArn=TOPIC_ARN,
            Subject="MediRescue: CRITICAL Emergency Alert",
            Message=json.dumps(item, default=str, indent=2),
        )

        return response(201, {
            "message": "Critical emergency stored and SNS hospital alert published",
            "emergency_id": item["emergency_id"],
            "notification": "SNS_PUBLISHED",
        })

    except Exception as error:
        print("ERROR:", repr(error))
        return response(500, {"error": str(error)})
