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
