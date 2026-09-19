"""Optional AWS integration for MediRescue.

The local SQLite database remains the development source of truth. When AWS is
configured, emergency events are mirrored to DynamoDB and an SNS notification
is published. This keeps the hackathon demo runnable locally while providing
real AWS usage in deployed environments.
"""
import os
from datetime import datetime, timezone
from decimal import Decimal

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # local development without AWS SDK
    boto3 = None
    BotoCoreError = ClientError = Exception

AWS_ENABLED = os.getenv("AWS_ENABLED", "false").lower() == "true"
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
DYNAMODB_TABLE = os.getenv("MEDIRESCUE_DYNAMODB_TABLE", "MediRescueEmergencies")
SNS_TOPIC_ARN = os.getenv("MEDIRESCUE_SNS_TOPIC_ARN", "")
ROUTES_ENABLED = os.getenv("MEDIRESCUE_ROUTES_ENABLED", "true").lower() == "true"

_dynamo_table = None
_sns = None
_routes = None


def _dynamodb_safe(value):
    """Convert Python floats recursively to Decimal for DynamoDB."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _dynamodb_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_dynamodb_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_dynamodb_safe(v) for v in value]
    return value


def _clients():
    global _dynamo_table, _sns
    if not AWS_ENABLED or boto3 is None:
        return None, None
    if _dynamo_table is None:
        resource = boto3.resource("dynamodb", region_name=AWS_REGION)
        _dynamo_table = resource.Table(DYNAMODB_TABLE)
    if _sns is None:
        _sns = boto3.client("sns", region_name=AWS_REGION)
    return _dynamo_table, _sns


def mirror_emergency(emergency_id, payload):
    """Mirror an emergency to DynamoDB; returns a small status object."""
    table, _ = _clients()
    if table is None:
        return {"enabled": False, "synced": False}
    item = {
        "emergency_id": str(emergency_id),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **{k: v for k, v in payload.items() if v is not None},
    }
    try:
        table.put_item(Item=_dynamodb_safe(item))
        return {"enabled": True, "synced": True}
    except (BotoCoreError, ClientError) as exc:
        return {"enabled": True, "synced": False, "error": str(exc)}


def notify(topic_message, subject="MediRescue Emergency"):
    """Publish an SNS message if a topic ARN is configured."""
    _, sns = _clients()
    if sns is None or not SNS_TOPIC_ARN:
        return {"enabled": False, "sent": False}
    try:
        sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject[:100], Message=topic_message)
        return {"enabled": True, "sent": True}
    except (BotoCoreError, ClientError) as exc:
        return {"enabled": True, "sent": False, "error": str(exc)}


def notify_critical_emergency(payload):
    """Send a structured AWS SNS alert for a new critical emergency.

    The SNS topic is intended to have hospital alert subscribers (email/SMS or
    an AWS-integrated notification service). The payload explicitly marks the
    event as CRITICAL and includes the nearest-hospital priority information.
    """
    import json

    message = {
        "notification_type": "NEW_CRITICAL_EMERGENCY",
        "severity": "CRITICAL",
        "service": "MediRescue",
        **{k: v for k, v in payload.items() if v is not None},
    }
    return notify(
        json.dumps(message, ensure_ascii=False, default=str, indent=2),
        subject="MediRescue: CRITICAL Emergency Alert",
    )


def calculate_route_eta(origin_latitude, origin_longitude, destination_latitude, destination_longitude):
    """Calculate road distance and travel time using Amazon Location Routes V2."""
    global _routes
    if not ROUTES_ENABLED or not AWS_ENABLED or boto3 is None:
        return None
    try:
        if any(v is None for v in (origin_latitude, origin_longitude, destination_latitude, destination_longitude)):
            return None
        if _routes is None:
            _routes = boto3.client("geo-routes", region_name=AWS_REGION)
        response = _routes.calculate_routes(
            Origin=[float(origin_longitude), float(origin_latitude)],
            Destination=[float(destination_longitude), float(destination_latitude)],
            TravelMode="Car", OptimizeRoutingFor="FastestRoute",
            Traffic={"Usage":"UseTrafficData"}, TravelStepType="TurnByTurn",
        )
        routes=response.get("Routes") or []
        if not routes: return None
        summary=routes[0].get("Summary") or {}
        if summary.get("Distance") is None or summary.get("Duration") is None: return None
        return {"distance_km":round(float(summary["Distance"])/1000.0,2),"eta_minutes":max(1,round(float(summary["Duration"])/60.0)),"source":"amazon_location_routes_v2"}
    except (BotoCoreError, ClientError, ValueError, TypeError, KeyError):
        return None
