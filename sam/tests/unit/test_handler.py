import json
import boto3
import os
import pytest

from unittest import mock

from thumbnail import app

from moto import mock_s3

BUCKET_NAME = "example-bucket"
KEY = "test/key"
IMAGE_FILE = "tests/corgi.jpg"
CALLBACK_URL_CORRECT = f"http://localhost:8000/async_image_upload/presignedurl/{KEY}/"
CALLBACK_URL_WRONG = "http://localhost:8000/async_image_upload/presignedurl/test/wrong_key/"
IMAGE_FOLDER = "image/"


@pytest.fixture
def default_env():
    """Mocked AWS Credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'ap-northeast-2'


@pytest.fixture
def default_env_with_blur_false():
    """Mocked AWS Credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'ap-northeast-2'
    os.environ['BLUR'] = "False"


@pytest.fixture
def default_env_with_blur_true():
    """Mocked AWS Credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'ap-northeast-2'
    os.environ['BLUR'] = "True"


@pytest.fixture
def s3_event():
    return {
      "Records": [
        {
          "eventVersion": "2.0",
          "eventSource": "aws:s3",
          "awsRegion": "ap-northeast-2",
          "eventTime": "1970-01-01T00:00:00.000Z",
          "eventName": "ObjectCreated:Put",
          "userIdentity": {
            "principalId": "EXAMPLE"
          },
          "requestParameters": {
            "sourceIPAddress": "127.0.0.1"
          },
          "responseElements": {
            "x-amz-request-id": "EXAMPLE123456789",
            "x-amz-id-2": "EXAMPLE123/5678abcdefghijklambdaisawesome/mnopqrstuvwxyzABCDEFGH"
          },
          "s3": {
            "s3SchemaVersion": "1.0",
            "configurationId": "testConfigRule",
            "bucket": {
              "name": BUCKET_NAME,
              "ownerIdentity": {
                "principalId": "EXAMPLE"
              },
              "arn": f"arn:aws:s3:::{BUCKET_NAME}"
            },
            "object": {
              "key": KEY,
              "size": 1024,
              "eTag": "0123456789abcdef0123456789abcdef",
              "sequencer": "0A1B2C3D4E5F678901"
            }
          }
        }
      ]
    }


def mocked_requests_put(*args, **kwargs):
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

    if args[0] == CALLBACK_URL_CORRECT:
        return MockResponse({"message": "ok"}, 200)
    if 'data' in kwargs:
        return MockResponse({"message": "ok"}, 200)

    return MockResponse(None, 404)


@mock.patch('thumbnail.app.requests.put', side_effect=mocked_requests_put)
@mock.patch('thumbnail.app.generate_thumbs', return_value=True)
def test_callback_success(mock_generate_thumbs, mock_requests, s3_event):
    ret = app.lambda_handler(s3_event, "")
    assert ret['resp']['message'] == "ok"
    assert ret['status_code'] == 200


@mock.patch('thumbnail.app.requests.put', side_effect=mocked_requests_put)
@mock.patch('thumbnail.app.generate_thumbs', side_effect=Exception('mocked error'))
def test_callback_fail(mock_generate_thumbs, mock_requests, s3_event):
    ret = app.lambda_handler(s3_event, "")
    assert "error" in ret


@mock_s3
class TestThumbnailFunction:
    s3 = None

    def setup_method(self, default_env):
        self.s3 = boto3.client('s3', region_name='ap-northeast-2')
        # bucket = boto3.resource('s3').Bucket(BUCKET_NAME)
        # bucket.objects.all().delete()
        # self.s3.delete_bucket(BUCKET_NAME)
        self.s3.create_bucket(
            Bucket=BUCKET_NAME,
            CreateBucketConfiguration={"LocationConstraint": "ap-northeast-2"}
        )

        with open(IMAGE_FILE, "rb") as f:
            # s3.put_object(Bucket='mybucket', Key=KEY, Body=f.read())
            self.s3.upload_file(IMAGE_FILE, BUCKET_NAME, KEY)
        ret = self.s3.get_object(Bucket=BUCKET_NAME, Key=KEY)

        assert ret['ResponseMetadata']['HTTPStatusCode'] == 200
        assert ret['ContentLength'] == 2903895

    @mock.patch('thumbnail.app.requests.put', side_effect=mocked_requests_put)
    def test_s3_thumbnail_without_blur_success(self, mock_requests, default_env_with_blur_false, s3_event):
        ret = app.lambda_handler(s3_event, "")
        assert ret['resp']['message'] == "ok"
        assert ret['status_code'] == 200

        ret = self.s3.list_objects_v2(Bucket=BUCKET_NAME)
        assert ret['ResponseMetadata']['HTTPStatusCode'] == 200
        assert "image/" in ret['Contents'][0]['Key']
        assert ret['KeyCount'] == 4

    @mock.patch('thumbnail.app.requests.put', side_effect=mocked_requests_put)
    def test_s3_thumbnail_with_blur_success(self, mock_requests, default_env_with_blur_true, s3_event):
        ret = app.lambda_handler(s3_event, "")
        assert ret['resp']['message'] == "ok"
        assert ret['status_code'] == 200

        ret = self.s3.list_objects_v2(Bucket=BUCKET_NAME)
        print(ret)
        assert ret['ResponseMetadata']['HTTPStatusCode'] == 200
        assert "image/" in ret['Contents'][0]['Key']
        assert ret['KeyCount'] == 8

    def teardown_method(self, default_env):
        bucket = boto3.resource('s3').Bucket(BUCKET_NAME)
        bucket.objects.all().delete()
        self.s3.delete_bucket(Bucket=BUCKET_NAME)

