import json
import os
import urllib.request

import boto3


ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION_NAME"))


def _webhook_url() -> str:
    parameter_name = os.environ["SLACK_WEBHOOK_PARAMETER"]
    response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
    return response["Parameter"]["Value"]


def _post_to_slack(text: str) -> None:
    body = json.dumps({"text": text}).encode("utf-8")
    request = urllib.request.Request(
        _webhook_url(),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        response.read()


def _format_alarm_message(message: dict) -> str:
    alarm_name = message.get("AlarmName", "unknown-alarm")
    new_state = message.get("NewStateValue", "UNKNOWN")
    reason = message.get("NewStateReason", "")
    trigger = message.get("Trigger", {})
    metric = trigger.get("MetricName", "metric")
    threshold = trigger.get("Threshold", "?")
    return f"Study_AWS-4 課題1: {alarm_name} is {new_state}. {metric} threshold={threshold}. {reason}"


def handler(event, _context):
    for record in event.get("Records", []):
        sns = record.get("Sns", {})
        message = json.loads(sns.get("Message", "{}"))
        _post_to_slack(_format_alarm_message(message))
    return {"status": "ok"}
