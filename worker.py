
import json
import time
import boto3

from app import create_app
from app.services.generation.generation_pipeline import (
    generate_project_video
)
from app.services.cloud.aws_storage import upload_file


app = create_app()

sqs = boto3.client(
    "sqs",
    region_name=app.config["AWS_DEFAULT_REGION"]
)

QUEUE_URL = app.config["SQS_QUEUE_URL"]


def process_message(message):
    body = json.loads(message["Body"])
    project_id = int(body["project_id"])

    print(f"Starting generation for project {project_id}")

    result = generate_project_video(project_id)

    output_path = result["output_video"]
    job_id = result["job_id"]

    object_key = (
        f"projects/{project_id}/jobs/{job_id}/final_reel.mp4"
    )

    s3_uri = upload_file(output_path, object_key)

    print(f"Generation completed: {output_path}")
    print(f"Uploaded to S3: {s3_uri}")


def run_worker():
    print("VidSnapAI SQS worker started.")

    while True:
        response = sqs.receive_message(
            QueueUrl=QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            VisibilityTimeout=900
        )

        for message in response.get("Messages", []):
            try:
                with app.app_context():
                    process_message(message)

                sqs.delete_message(
                    QueueUrl=QUEUE_URL,
                    ReceiptHandle=message["ReceiptHandle"]
                )

                print("Message processed and removed from queue.")

            except Exception as exc:
                print(f"Worker failed: {exc}")

                # The generation pipeline records its own failure.
                # Remove the failed message to avoid endless retries.
                sqs.delete_message(
                    QueueUrl=QUEUE_URL,
                    ReceiptHandle=message["ReceiptHandle"]
                )

        time.sleep(1)


if __name__ == "__main__":
    run_worker()
