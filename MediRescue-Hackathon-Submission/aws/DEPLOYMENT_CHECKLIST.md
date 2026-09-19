# AWS deployment checklist

- [ ] Configure AWS CLI credentials
- [ ] Install AWS SAM CLI
- [ ] `cd aws && sam build`
- [ ] `sam deploy --guided`
- [ ] Verify API Gateway `/health`
- [ ] Verify Lambda CloudWatch logs
- [ ] Verify DynamoDB emergency item
- [ ] Verify SNS publish
- [ ] Only then migrate the next API group
