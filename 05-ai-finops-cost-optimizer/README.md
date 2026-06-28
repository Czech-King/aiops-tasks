=======================================================================
TASK 05 — AI-DRIVEN FINOPS & COST OPTIMIZER
Production Grade DevOps & AI Project — Complete Guide
Console Based Setup & Serverless Architecture
=======================================================================

WHY WE ARE DOING THIS TASK & WHAT WE WILL ACHIEVE
=======================================================================
Cloud bills can spiral out of control overnight. A developer might leave 
a massive EC2 instance running, or a misconfigured Lambda might loop infinitely, 
resulting in thousands of dollars in NAT Gateway charges.

By building an "AI FinOps Optimizer", we achieve:
1. Daily Cost Profiling: AWS Cost Explorer API is queried every morning.
2. AI Spending Analysis: AWS Bedrock compares yesterday's spend to the 7-day average. It detects anomalies (e.g., "S3 bandwidth spiked by 400%").
3. Automated Recommendations: The AI generates specific, actionable recommendations to cut costs (e.g., "Add an S3 VPC Endpoint to reduce NAT charges").
4. Executive Reporting: A formatted FinOps report is automatically emailed to Engineering Managers via Amazon SNS.

ARCHITECTURE
=======================================================================
Amazon EventBridge (Triggers daily at 8:00 AM)
       ↓
AWS Lambda (Python 3.11)
       ↓ (Queries AWS Cost Explorer API for previous 7 days)
AWS Bedrock (Analyzes JSON cost data for spikes & optimizations)
       ↓
Amazon SNS (Sends beautifully formatted Email/Slack message)

=======================================================================
PART 1 — COST EXPLORER & SNS SETUP
=======================================================================

Step 1 — Enable Cost Explorer
AWS Console → Billing and Cost Management → Cost Explorer. (If already enabled, skip — no action needed.)

Step 2 — Create the SNS Topic
Why: Simple Notification Service (SNS) allows us to securely broadcast 
our AI reports to multiple email addresses.
1. AWS Console -> SNS -> Topics -> Create topic.
2. Type: Standard. Name: `Daily-FinOps-Reports`.
3. Create Topic.
4. Click Create subscription -> Protocol: Email -> Endpoint: `manager@yourcompany.com`.
5. Check your email and click the confirmation link.
6. SAVE the Topic ARN.

=======================================================================
PART 3 — THE AI FINOPS LAMBDA
=======================================================================

Step 3 — Create the Lambda Function
1. AWS Console -> Lambda -> Create function: `FinOps-AI-Analyzer`.
2. Runtime: Python 3.11. Timeout: 1 minute.
3. IAM Role Attachments:
   - `AWSBillingReadOnlyAccess` (covers Cost Explorer)
   - `AmazonBedrockFullAccess`
   - `AmazonSNSFullAccess`
4. Environment Variables:
   - `SNS_TOPIC_ARN` = `<your-topic-arn>`

Step 4 — Write the Analysis Logic
Why: The code must calculate date ranges, fetch granular cost data, and 
prompt the AI effectively.

Code `lambda_function.py`:
```python
import json, os, boto3, re
from datetime import datetime, timedelta

ce = boto3.client('ce', region_name='ap-south-1')
bedrock = boto3.client('bedrock-runtime', region_name='ap-south-1')
sns = boto3.client('sns', region_name='ap-south-1')

def lambda_handler(event, context):
    # 1. Calculate Date Ranges (Last 7 days)
    end_date = datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.today() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    # 2. Fetch Cost Data grouped by AWS Service
    res = ce.get_cost_and_usage(
        TimePeriod={'Start': start_date, 'End': end_date},
        Granularity='DAILY',
        Metrics=['UnblendedCost'],
        GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
    )
    
    # Capture all costs (including fractions of a cent for test accounts)
    cost_data = []
    for day in res['ResultsByTime']:
        day_cost = {"Date": day['TimePeriod']['Start'], "Services": {}}
        for group in day['Groups']:
            amount = float(group['Metrics']['UnblendedCost']['Amount'])
            if amount > 0.001:  # Capture even tiny costs for testing
                day_cost["Services"][group['Keys'][0]] = round(amount, 4)
        cost_data.append(day_cost)
        
    # 3. Analyze with Bedrock
    prompt = f"""
    You are an Expert AWS FinOps Architect. Analyze the last 7 days of AWS spend:
    {json.dumps(cost_data)}
    
    Write a daily AWS Cost Report email with these sections:
    
    DAILY AWS FINOPS REPORT
    Period: {start_date} to {end_date}
    ============================================================
    
    1. SPEND SUMMARY
    (Total spend, daily trend, highest spend day)
    
    2. TOP SERVICES BY COST
    (List each service, its total cost, and % of total bill)
    
    3. ANOMALIES DETECTED
    (Any unusual spikes or patterns)
    
    4. TOP 3 RECOMMENDATIONS
    (Specific, actionable steps to reduce cost)
    
    IMPORTANT FORMATTING RULES:
    - Use PLAIN TEXT ONLY. No markdown, no **, no ##, no asterisks.
    - Use ALL CAPS for section headers.
    - Use dashes (-) for bullet points.
    - Separate sections with a line of dashes (---).
    - Keep it concise, professional, and easy to read in an email.
    """
    
    response = bedrock.invoke_model(
        modelId='openai.gpt-oss-safeguard-120b',
        body=json.dumps({"messages": [{"role": "user", "content": prompt}]}),
        contentType='application/json'
    )
    
    response_data = json.loads(response['body'].read().decode())
    report = response_data['choices'][0]['message']['content']
    report = re.sub(r'<reasoning>.*?</reasoning>', '', report, flags=re.DOTALL).strip()
    report = report.lstrip(': \n')
    
    # 4. Email via SNS
    sns.publish(
        TopicArn=os.environ['SNS_TOPIC_ARN'],
        Subject="Daily AI FinOps Report",
        Message=report
    )
    
    return {"statusCode": 200, "body": "Report Sent"}
```

=======================================================================
PART 4 — EVENTBRIDGE SCHEDULING
=======================================================================

Step 5 — Automate the execution
Why: FinOps is only effective if it happens proactively every day.
1. AWS Console -> EventBridge -> Create rule.
2. Name: `Daily-FinOps-Trigger`.
3. Rule type: Schedule -> Cron expression.
4. Cron: `0 8 * * ? *` (8:00 AM UTC daily).
5. Target: Lambda function `FinOps-AI-Analyzer`.
6. Click Create.

=======================================================================
PART 5 — TESTING
=======================================================================

Step 6 — Test the pipeline
1. Go to your Lambda function and click "Test".
2. Check your email inbox.
3. Observation: You will receive a beautifully formatted email:
   **Subject: Daily AI FinOps Report**
   *Spend Trend:* Your total spend increased by 15% yesterday, driven primarily by Amazon EC2.
   *Anomalies:* "EC2 - Other" costs (NAT Gateway Data Processing) spiked from $10/day to $45 yesterday.
   *Recommendations:*
   1. The NAT Gateway spike suggests an internal resource is downloading large files from S3. Implement an S3 Gateway VPC Endpoint to route this traffic for free.
   2. Ensure auto-scaling groups are scaling down during off-peak hours.

=======================================================================
CLEANUP
=======================================================================
1. Delete EventBridge Rule.
2. Delete Lambda.
3. Delete SNS Topic.
