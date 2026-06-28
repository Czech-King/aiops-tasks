# AI-Driven FinOps & Cost Optimizer

An automated, serverless cost optimization system built with AWS Lambda, EventBridge, AWS Cost Explorer, AWS Bedrock (`openai.gpt-oss-safeguard-120b`), and Amazon SNS.

Every morning, the optimizer queries the AWS Cost Explorer API for cost trends over the past 7 days, aggregates the costs, sends the raw spending report to AWS Bedrock to identify anomalies and suggest cost-saving recommendations, and emails a clean plain-text executive report to engineering managers via SNS.

---

## Architecture Diagram

```
[EventBridge Cron (Daily 8AM)]
              │
              ▼
        [AWS Lambda]
              │
              ├─► [Query AWS Cost Explorer API]
              ├─► [Invoke AWS Bedrock (Analysis & Recommendations)]
              └─► [Publish Email to Amazon SNS Topic]
```

---

## Directory Structure

```
.
├── README.md
└── src/
    └── lambda_function.py      # Core Lambda handler and cost analyzer logic
```

---

## Setup & Deployment Guide

Please refer to the main walkthrough file [05-AI-FinOps-CostOptimizer.md](../05-AI-FinOps-CostOptimizer.md) for full instructions on setting up Cost Explorer, SNS, IAM roles, and Lambda variables.
