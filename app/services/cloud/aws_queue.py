import json
import boto3
from flask import current_app


def enqueue_generation(project_id):
    sqs = boto3.client(
        "sqs",
        region_name=current_app.config["AWS_DEFAULT_REGION"]
    )

    response = sqs.send_message(
        QueueUrl=current_app.config["SQS_QUEUE_URL"],
        MessageBody=json.dumps({
            "project_id": project_id,
            "task": "generate_video"
        })
    )

    return response["MessageId"]