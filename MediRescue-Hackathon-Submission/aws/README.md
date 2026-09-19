# MediRescue AWS Foundation

This is **AWS Phase 1**. The working local Flask/SQLite demo remains intact; this layer adds a small, deployable serverless foundation before migrating the full API.

## Resources
- API Gateway HTTP API
- AWS Lambda (Python 3.13)
- DynamoDB `MediRescueEmergencies`
- SNS `MediRescueEmergencyAlerts`

## Endpoints
- `GET /health`
- `POST /emergencies` — stores an emergency snapshot in DynamoDB and publishes an SNS event.

## Deploy
Prerequisites: AWS CLI, configured credentials, and AWS SAM CLI.

```bash
cd aws
sam build
sam deploy --guided
```

After deployment, use the `ApiUrl` output and test `/health`, then POST a test emergency.

## Migration order
1. Deploy this foundation and verify DynamoDB/SNS.
2. Migrate emergency state + timeline events.
3. Migrate hospital/driver APIs.
4. Add Cognito authentication.
5. Point the frontend to API Gateway.
6. Add Bedrock only after the core AWS flow is stable.
