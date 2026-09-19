# AWS-powered hospital emergency alerts

MediRescue uses **Amazon SNS** for the external hospital alert layer.

When a patient SOS is confirmed:

1. The Flask API calculates the nearest verified/online hospital.
2. The nearest hospital is assigned priority #1.
3. The emergency snapshot is mirrored to DynamoDB when AWS is enabled.
4. An SNS message is published with `notification_type=NEW_CRITICAL_EMERGENCY` and `severity=CRITICAL`.
5. Hospital alert subscribers receive the message (email/SMS or another AWS notification integration).

## AWS Console setup

After `sam deploy --guided`:

1. Open **Amazon SNS → Topics → MediRescueEmergencyAlerts**.
2. Choose **Create subscription**.
3. For a demo, choose `Email` and enter the hospital emergency/command-center email.
4. Open the confirmation email and confirm the subscription.
5. Repeat for each hospital command center that should receive the alert stream.

The SNS topic is intentionally shared so every subscribed command center can receive the critical event, while the MediRescue payload identifies the **priority #1 nearest hospital**. The local hospital UI still shows the ranked queue and response controls.

## Local configuration

Set these values in `.env` (or your deployment environment):

```text
AWS_ENABLED=true
AWS_REGION=ap-south-1
MEDIRESCUE_DYNAMODB_TABLE=MediRescueEmergencies
MEDIRESCUE_SNS_TOPIC_ARN=<SNS topic ARN from CloudFormation output>
```

The local app remains usable when `AWS_ENABLED=false`; in that mode the AWS notification result reports disabled instead of blocking the SOS flow.
