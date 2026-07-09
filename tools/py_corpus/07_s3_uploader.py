import boto3

def upload_file(bucket, key, path):
    client = boto3.client("s3")
    client.upload_file(path, bucket, key)
    return "s3://" + bucket + "/" + key

def list_keys(bucket, prefix=""):
    client = boto3.client("s3")
    resp = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    return [obj["Key"] for obj in resp.get("Contents", [])]
