import boto3
from flask import current_app


def upload_file(file_path, object_key):
    bucket = current_app.config["S3_BUCKET_NAME"]

    s3 = boto3.client(
        "s3",
        region_name=current_app.config["AWS_DEFAULT_REGION"]
    )

    s3.upload_file(
        str(file_path),
        bucket,
        object_key,
        ExtraArgs={"ContentType": "video/mp4"}
    )

    return f"s3://{bucket}/{object_key}"