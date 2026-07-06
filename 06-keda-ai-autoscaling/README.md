=======================================================================
TASK 06 — EVENT-DRIVEN AUTOSCALING WITH KEDA & AI
Production Grade DevOps & AI Project — Complete Guide
Kubernetes Scalability & SQS Architecture
=======================================================================

WHY WE ARE DOING THIS TASK & WHAT WE WILL ACHIEVE
=======================================================================
Kubernetes natively uses the Horizontal Pod Autoscaler (HPA) to scale pods 
based on CPU and Memory. But what if your worker pod is just waiting for 
an AI task to finish? CPU is at 1%, but there are 10,000 tasks in the queue! 
Standard HPA fails here, and the queue backs up.

By building an "Event-Driven KEDA Autoscaler", we achieve:
1. Zero-to-Scale: Scale pods down to zero when there is no work to save money, and scale up instantly when work arrives.
2. Queue-Based Scaling: KEDA hooks directly into AWS SQS. Instead of looking at CPU, it looks at the queue length (e.g., 1 pod per 10 messages).
3. Advanced Authentication: We use AWS IRSA to securely grant KEDA permission to read the SQS queue depth without hardcoded keys.

ARCHITECTURE
=======================================================================
User drops PDF/AI requests into S3
       ↓
Amazon SQS (Queue length goes from 0 to 500)
       ↓
KEDA Metrics Server (Running in EKS, queries SQS `ApproximateNumberOfMessagesVisible`)
       ↓
Kubernetes HPA (Commanded by KEDA to scale the deployment)
       ↓
EKS Worker Pods scale from 0 to 50
       ↓ (Queue empties)
EKS Worker Pods scale back to 0.

=======================================================================
PART 1 — INSTALLING KEDA ON EKS
=======================================================================

Step 1 — Create the KEDA IAM Role
Why: KEDA needs to securely authenticate to AWS to check the queue length.
```bash
eksctl create iamserviceaccount \
  --cluster=my-cluster \
  --name=keda-operator \
  --namespace=keda \
  --attach-policy-arn=arn:aws:iam::aws:policy/AmazonSQSReadOnlyAccess \
  --approve \
  --role-name=eks-keda-operator
```

Step 2 — Install KEDA via Helm
Why: We install KEDA using the official Helm chart and link it to our existing IAM-enabled ServiceAccount.
```bash
helm repo add kedacore https://kedacore.github.io/charts
helm repo update

helm install keda kedacore/keda \
  --namespace keda \
  --create-namespace \
  --set serviceAccount.operator.create=false \
  --set serviceAccount.operator.name=keda-operator
```
Wait for the KEDA operator pods to reach `Running` state: `kubectl get pods -n keda`.

=======================================================================
PART 2 — AWS INFRASTRUCTURE
=======================================================================

Step 3 — Create the Target SQS Queue
1. AWS Console -> SQS -> Create queue.
2. Name: `ai-task-queue`.
3. Type: Standard.
4. Copy the Queue URL (e.g., `https://sqs.us-east-1.amazonaws.com/123/ai-task-queue`).

=======================================================================
PART 3 — APPLICATION AND AUTOSCALER YAML
=======================================================================

Step 4 — Deploy the Dummy Worker
Why: We need an application to scale. We deploy it initially with 0 replicas.

Create `worker-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-worker
spec:
  replicas: 0 # CRITICAL: Start at zero!
  selector:
    matchLabels:
      app: ai-worker
  template:
    metadata:
      labels:
        app: ai-worker
    spec:
      containers:
      - name: worker
        image: python:3.11-slim
        # A dummy script that just sleeps, pretending to process queue items
        command: ["/bin/sh"]
        args: ["-c", "while true; do echo 'Polling SQS...'; sleep 10; done"]
```
`kubectl apply -f kubernetes/worker-deployment.yaml`

Step 5 — Create the KEDA ScaledObject
Why: This Custom Resource Definition (CRD) is what connects our Kubernetes 
deployment to the AWS SQS queue.

Create `scaledobject.yaml`:
```yaml
apiVersion: keda.sh/v1alpha1
kind: TriggerAuthentication
metadata:
  name: aws-sqs-auth
  namespace: default
spec:
  podIdentity:
    provider: aws # Tells KEDA to use the attached IRSA role
---
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: aws-sqs-scaledobject
  namespace: default
spec:
  scaleTargetRef:
    name: ai-worker
  minReplicaCount: 0 # Scale to 0 when idle
  maxReplicaCount: 50 # Prevent scaling infinitely
  pollingInterval: 10 # Check queue every 10 seconds
  cooldownPeriod: 60  # Wait 60s before scaling back down to 0
  triggers:
  - type: aws-sqs-queue
    authenticationRef:
      name: aws-sqs-auth
    metadata:
      queueURL: "https://sqs.us-east-1.amazonaws.com/032080729357/ai-task-queue"
      queueLength: "5" # Target: 1 pod for every 5 messages
      awsRegion: "us-east-1"
```
`kubectl apply -f kubernetes/scaledobject.yaml`

=======================================================================
PART 4 — TESTING THE AUTO-SCALING
=======================================================================

Step 6 — Verify Zero State
1. Run: `kubectl get pods`.
2. Observation: There are NO `ai-worker` pods running. Your compute cost is currently $0.

Step 7 — Inject Load
Why: We will artificially send 100 messages into SQS to simulate a massive 
spike in user traffic.

1. Open a terminal and use the AWS CLI to flood the queue:
```bash
for i in {1..100}; do
  aws sqs send-message --queue-url "https://sqs.us-east-1.amazonaws.com/032080729357/ai-task-queue" --message-body "Task $i"
done
```

''' delete Q

aws sqs purge-queue --queue-url "https://sqs.us-east-1.amazonaws.com/032080729357/ai-task-queue"


'''
2. Immediately watch the pods: `kubectl get pods -w`
3. Observation: 
   - KEDA sees 100 messages. 
   - Target is 1 pod per 5 messages.
   - KEDA instantly signals the HPA to scale from 0 to 20 pods.
   - You will see 20 `ai-worker` pods spin up simultaneously!

Step 8 — Empty the Queue
1. Purge the SQS queue in the AWS Console.
2. Wait 60 seconds (the `cooldownPeriod`).
3. Run `kubectl get pods`.
4. Observation: All pods are terminating. KEDA has gracefully scaled the deployment back to 0.

=======================================================================
CLEANUP
=======================================================================
1. `kubectl delete -f kubernetes/scaledobject.yaml`
2. `kubectl delete -f kubernetes/worker-deployment.yaml`
3. Delete SQS Queue.
4. `helm uninstall keda -n keda`
