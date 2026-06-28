=======================================================================
TASK 04 — AI-DRIVEN CLOUD SECURITY THREAT DETECTION
Production Grade DevOps & AI Project — Complete Guide
Console Based Setup & Python Lambda
=======================================================================

WHY WE ARE DOING THIS TASK & WHAT WE WILL ACHIEVE
=======================================================================
AWS GuardDuty and CloudTrail detect thousands of events daily. When a developer 
logs in without MFA, or an EC2 instance communicates with a known malicious IP, 
Security teams receive raw JSON alerts. These alerts are cryptic and hard to 
prioritize, leading to "Alert Fatigue".

By building an "AI Threat Detection Pipeline", we achieve:
1. Automated Threat Analysis: Every GuardDuty finding is intercepted in real-time.
2. AI Contextualization: AWS Bedrock reads the cryptic JSON (IPs, APIs, User ARNs) and translates it into a human-readable threat summary, assessing the true risk based on your specific environment.
3. Actionable ChatOps: Slack receives the AI summary, along with immediate remediation steps (e.g., "The AI recommends revoking session tokens for user Bob immediately").

ARCHITECTURE
=======================================================================
AWS GuardDuty (Detects anomalous behavior)
       ↓
Amazon EventBridge (Filters for High/Medium Severity)
       ↓
AWS Lambda (Python)
       ↓ (Sends raw JSON to Bedrock openai.gpt-oss-safeguard-120b)
AWS Bedrock (Generates Risk Assessment and Remediation)
       ↓
Slack Webhook (Posts actionable alert to #security-ops)

=======================================================================
PART 1 — GUARDDUTY & EVENTBRIDGE SETUP
=======================================================================

Step 1 — Enable Amazon GuardDuty
Why: GuardDuty uses AWS-managed machine learning to detect compromised 
credentials, crypto-mining EC2s, and malicious IP traffic.
1. AWS Console -> GuardDuty -> Get Started -> Enable GuardDuty.

Step 2 — Create EventBridge Rule
Why: We don't want to wake up the Lambda for low-severity issues. We only 
trigger our AI for Medium (4.0+) to High (7.0+) severity alerts.
1. AWS Console -> EventBridge -> Create rule.
2. Name: `High-Severity-GuardDuty`.
3. Event pattern:
```json
{
  "source": ["aws.guardduty"],
  "detail-type": ["GuardDuty Finding"],
  "detail": {
    "severity": [
      4, 4.0, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9,
      5, 5.0, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9,
      6, 6.0, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9,
      7, 7.0, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9,
      8, 8.0, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9,
      9, 9.0, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9
    ]
  }
}
```
4. Target: AWS Lambda function (we will create this next).

=======================================================================
PART 2 — AI THREAT ANALYZER LAMBDA
=======================================================================

Step 3 — Create the Lambda Function
1. AWS Console -> Lambda -> Create function: `GuardDuty-AI-Analyzer`.
2. Runtime: Python 3.11.
3. IAM Role: Attach `AmazonBedrockFullAccess`.
4. Environment Variables: `SLACK_WEBHOOK` = `<your-slack-url>`.

Step 4 — Write the AI Logic
Why: The Lambda must parse the finding, formulate a strong prompt, and 
pass it to Bedrock.

Code `lambda_function.py`:
```python
import json, os, urllib.request, boto3, re, time, random

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

# ── Severity metadata: color bar + emoji badge + severity progress bar ──────
def get_severity_meta(sev):
    sev = float(sev)
    filled  = int(sev)                          # e.g. 8.0 → 8 filled blocks
    bar     = "█" * filled + "░" * (10 - filled)
    if sev >= 7.0:
        return {"color": "#FF0000", "emoji": "🚨", "label": "CRITICAL", "bar": bar}
    elif sev >= 4.0:
        return {"color": "#FF8C00", "emoji": "⚠️",  "label": "HIGH",     "bar": bar}
    else:
        return {"color": "#FFD700", "emoji": "🔔", "label": "MEDIUM",   "bar": bar}

def lambda_handler(event, context):
    finding      = event['detail']
    severity     = finding.get('severity', 0)
    title        = finding.get('title', 'Unknown')
    description  = finding.get('description', '')
    finding_type = finding.get('type', 'Unknown')
    account_id   = finding.get('accountId', 'Unknown')
    region       = finding.get('region', 'Unknown')
    finding_id   = finding.get('id', 'N/A')
    updated_at   = finding.get('updatedAt', 'N/A')

    # ── NOISE FILTER: only HIGH (7.0+) reaches Slack ─────────────────────────
    # GuardDuty sample findings fires ~150 alerts; this cuts it to ~20 HIGH ones
    if float(severity) < 7.0:
        print(f"Skipped severity {severity} — below threshold")
        return {"statusCode": 200, "body": f"Skipped severity {severity}"}

    # ── RATE LIMITER: random jitter sleep to stagger parallel Slack posts ─────
    # Each Lambda invocation sleeps a different amount so messages arrive spaced
    jitter = random.uniform(1, 8)   # 1–8 second random delay
    print(f"Rate limiter: sleeping {jitter:.1f}s before posting to Slack")
    time.sleep(jitter)

    resource_data = json.dumps(finding.get('resource', {}), indent=2)
    meta = get_severity_meta(severity)

    # ── PROMPT: forces exact 5-line output, no prose, no preamble ────────────
    prompt = f"""You are a senior AWS Security Engineer. Respond in EXACTLY this format — no intro, no extra text:

🔍 *What happened:* [1 sentence, plain English — what the attacker did]
💥 *Business impact:* [1 sentence — worst case if not fixed in 1 hour]
🛠️ *Fix step 1:* [exact AWS CLI command]
🛠️ *Fix step 2:* [exact AWS CLI command]
🛠️ *Fix step 3:* [exact AWS CLI command or console action]

Finding details:
Severity: {severity}/10 | Type: {finding_type}
Title: {title}
Description: {description}
Resource JSON: {resource_data}"""

    # ── BEDROCK CALL ──────────────────────────────────────────────────────────
    response = bedrock.invoke_model(
        modelId='openai.gpt-oss-safeguard-120b',
        body=json.dumps({"messages": [{"role": "user", "content": prompt}]}),
        contentType='application/json'
    )
    response_data = json.loads(response['body'].read().decode())
    ai_analysis   = response_data['choices'][0]['message']['content']

    # Strip model reasoning blocks if any
    ai_analysis = re.sub(r'<reasoning>.*?</reasoning>', '', ai_analysis, flags=re.DOTALL).strip()
    ai_analysis = ai_analysis.lstrip(': \n')

    # ── SLACK BLOCK KIT: rich colorful card ───────────────────────────────────
    slack_payload = {
        "attachments": [
            {
                "color": meta["color"],   # colored left border (red/orange/yellow)
                "blocks": [
                    # ── HEADER BANNER ──────────────────────────────────────────
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"{meta['emoji']}  {meta['label']} ALERT  |  Severity {severity}/10  |  GuardDuty"
                        }
                    },
                    # ── SEVERITY PROGRESS BAR ──────────────────────────────────
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Severity:* `{meta['bar']}` *{severity}/10*"
                        }
                    },
                    {"type": "divider"},
                    # ── METADATA GRID ──────────────────────────────────────────
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"🏦 *Account*\n`{account_id}`"},
                            {"type": "mrkdwn", "text": f"🌍 *Region*\n`{region}`"},
                            {"type": "mrkdwn", "text": f"🏷️ *Type*\n`{finding_type.split('/')[-1]}`"},
                            {"type": "mrkdwn", "text": f"🕐 *Detected*\n`{updated_at[:19] if updated_at != 'N/A' else 'N/A'}`"}
                        ]
                    },
                    # ── FINDING TITLE ──────────────────────────────────────────
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"📋 *Finding:*\n>{title}"
                        }
                    },
                    {"type": "divider"},
                    # ── AI ANALYSIS ────────────────────────────────────────────
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"🤖 *AI Threat Analysis*\n\n{ai_analysis}"
                        }
                    },
                    {"type": "divider"},
                    # ── FOOTER ─────────────────────────────────────────────────
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"🔑 Finding ID: `{finding_id[:20]}...`  |  Powered by AWS GuardDuty + Bedrock AI"
                            }
                        ]
                    }
                ]
            }
        ]
    }

    req = urllib.request.Request(
        os.environ['SLACK_WEBHOOK'],
        data=json.dumps(slack_payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    urllib.request.urlopen(req)

    return {"statusCode": 200, "body": f"Alert sent for severity {severity}"}
```

=======================================================================
PART 3 — TESTING THE SECURITY PIPELINE
=======================================================================

Step 5 — Generate GuardDuty Sample Findings
Why: We must verify that the AI can interpret a real attack scenario.
1. AWS Console -> GuardDuty -> Settings.
2. Scroll to "Sample findings" -> Click Generate sample findings.
3. GuardDuty will inject ~20 fake alerts (some High, some Low).
4. EventBridge will catch the High severity ones and trigger Lambda.

Step 6 — Verify Slack Output
Observation: Slack receives messages like:

🚨 **AWS Security Threat Detected (Severity 8.0)**
**Threat Analysis:** 
An EC2 instance in your environment is querying a domain known to be associated with Bitcoin mining. This indicates the instance has likely been compromised via an RCE (Remote Code Execution) or exposed SSH port.

**Business Risk:**
CRITICAL. The attacker is consuming your AWS compute resources, which will lead to a massive unexpected AWS bill. Furthermore, they may pivot to other resources in the VPC.

**Immediate Remediation:**
1. Isolate the Instance:
   `aws ec2 modify-instance-attribute --instance-id i-12345 --groups sg-isolated`
2. Revoke IAM Role Temp Credentials:
   `aws iam put-role-policy --role-name <InstanceRole> --policy-name DenyAll --policy-document ...`
3. Snapshot the Volume for Forensics:
   `aws ec2 create-snapshot --volume-id vol-67890`

=======================================================================
CLEANUP
=======================================================================
1. Disable GuardDuty (if not needed for production).
2. Delete EventBridge Rule.
3. Delete Lambda Function.
