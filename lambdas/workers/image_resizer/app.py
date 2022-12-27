from typing import Tuple
import os
import boto3
import json
from PIL import Image


s3Client = boto3.client('s3')


def clear_local_tmp_file_cache(file_path: str):
    """
    Clear the /tmp folder
    Lambda shaers the /tmp folder between invocations
    """
    if os.path.exists(file_path):
        os.remove(file_path)


def download_file_from_s3(bucket: str, key: str, file_path: str):
    """Download a file from S3"""
    with open(file_path, 'wb') as f:
        s3Client.download_fileobj(bucket, key, f)


def upload_file_to_s3(bucket: str, key: str, file_path: str, ACL: str = 'private') -> dict:
    """Upload a file to S3"""
    with open(file_path, 'rb') as f:
        resp = s3Client.put_object(Body=f, Bucket=bucket, Key=key, ACL=ACL)
        return resp


def resize_image(source_image_path: str, destination_image_path: str, new_size: Tuple[int, int]) -> None:
    """Resize image to fit in the given size while keeping the aspect ratio"""
    with Image.open(source_image_path) as image:
        image.thumbnail(new_size)
        image.save(destination_image_path)


def lambda_handler(event, context):
    """
    Accepts a source and dest S3 object keys (and bucket)
    Resize the image and move it to its new destination
    First, it creates new image and only on success it removes the former one
    """

    try:
        original_file_key = event['source_file_key']
        file_name = original_file_key.split('/')[-1]
        temp_file_path = f'/tmp/{file_name}'
        new_file_path = f'/tmp/modified_{file_name}'

        clear_local_tmp_file_cache(file_path=temp_file_path)

        clear_local_tmp_file_cache(file_path=new_file_path)

        download_file_from_s3(bucket=event['source_bucket'], key=original_file_key, file_path=temp_file_path)

        resize_image(
            source_image_path=temp_file_path,
            destination_image_path=new_file_path,
            size=tuple(event['new_size'])
        )

        print('Going to upload resized image: ' + event['dest_bucket'] + '/' + event['dest_file_key'])
        upload_file_to_s3(
            bucket=event['dest_bucket'],
            key=event['dest_file_key'],
            file_path=new_file_path,
            ACL=event.get('ACL', 'private')
        )
        print('Resized imaged has been uploaded')

    except Exception as e:
        print('Exception')
        print(e)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

    return {
        'statusCode': 200,
        'body': json.dumps('Processing complete successfully')
    }

