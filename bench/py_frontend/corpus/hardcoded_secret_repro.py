# Real-world shape — hardcoded credential (CWE-798).
#
# The single most common finding in real repository scans: a provider
# key committed as a string literal. It survives review because the line
# looks like configuration, and it stays valid long after the commit is
# reverted, because git history keeps it.
#
# CWE-798. Aether's E0723 is a literal-CONTENT scan (a secret scanner in
# the compiler), not a dataflow check — it matches narrow, high-confidence
# provider shapes rather than guessing at entropy.
#
# The vulnerable shape:

import boto3


def make_client():
    # A real AWS access key ID shape. Committed, and now permanent.
    access_key = "AKIAIOSFODNN7EXAMPLE"
    return boto3.client("s3", aws_access_key_id=access_key)


# The fix: the credential is supplied by the environment (or a secret
# manager) and never exists in the source.

import os


def make_client_safe():
    access_key = os.environ["AWS_ACCESS_KEY_ID"]
    return boto3.client("s3", aws_access_key_id=access_key)


# In Aether this maps 1:1 onto E0723:
#   let k: String = "AKIA..."       -> E0723 (literal matches a provider shape)
#   let k: String = getEnv("...")   -> clean
