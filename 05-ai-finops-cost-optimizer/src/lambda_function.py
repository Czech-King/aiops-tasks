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
