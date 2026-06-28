# AIOPS Tasks

Welcome to the **AIOPS Tasks** repository. This repository hosts a collection of production-grade DevOps, GitOps, and AI-driven automation projects.

## Projects Index

| Task / Day | Project Name | Description |
| :--- | :--- | :--- |
| **01** | [01-gitlab-ai-code-reviewer](./01-gitlab-ai-code-reviewer) | Automated, event-driven Merge Request code reviewer using AWS Lambda, API Gateway, and AWS Bedrock (`openai.gpt-oss-safeguard-120b`). |
| **02** | [02-eks-aiops-log-anomaly](./02-eks-aiops-log-anomaly) | Real-time log streaming using Fluent Bit, AWS Kinesis Data Streams, and AWS Lambda processing anomalies with AWS Bedrock to alert on Slack. |
| **03** | [03-mlops-sagemaker-argocd](./03-mlops-sagemaker-argocd) | Production-grade MLOps pipeline automating model training on AWS SageMaker and continuous GitOps deployment to Amazon EKS via ArgoCD. |
| **04** | [04-ai-security-threat-detection](./04-ai-security-threat-detection) | AI-Driven Cloud Security Threat Detection analyzing GuardDuty findings via EventBridge, Lambda, and Bedrock to alert on Slack. |
| **05** | [05-ai-finops-cost-optimizer](./05-ai-finops-cost-optimizer) | AI-Driven FinOps & Cost Optimizer analyzing daily AWS spend using Cost Explorer and Bedrock to send SNS reports. |

---

## Repository Structure

Each project is contained in its own self-contained directory with source code, Terraform infrastructure code (where applicable), and a detailed setup/deployment guide.
