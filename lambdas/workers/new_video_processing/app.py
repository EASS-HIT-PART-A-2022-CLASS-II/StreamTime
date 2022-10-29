from typing import Dict, Tuple
import json
import subprocess
import shlex
import boto3
import os
import datetime

# PROCESSING_STATES
READY = 'READY'
FAILED = 'DELETED'

# NOTES
INTERNAL_ERROR_PLEASE_TRY_AGAIN_LATER = 'INTERNAL_ERROR_PLEASE_TRY_AGAIN_LATER'
MAX_FILE_SIZE_OVERFLOW = 'MAX_FILE_SIZE_OVERFLOW'
CORRUPTED = 'CORRUPTED'
NOT_A_VIDEO_TYPE = 'NOT_A_VIDEO_TYPE'
AWAIT_FOR_REGISTRATION = 'AWAIT_FOR_REGISTRATION'

# CONSTANTS
EXECUTABLES_DIRECTORY = '/opt/var/task/python'

THUMBNAIL_SIZE = (360, 200)

S3_THUMBNAILS_ACL_ENV_NAME = 's3_thumbnails_acl'
S3_MAX_VIDEO_SIZE_IN_BYTES_ENV_NAME = 's3_max_video_file_size_in_bytes'
IMAGE_RESIZER_LAMBDA_ARN_ENV_NAME = 'image_resizer_lambda_arn'
THUMBNAILS_PREFIX_ENV_NAME = 's3_thumbnails_prefix'
UNREGISTERED_VIDEOS_PREFIX_ENV_NAME = 's3_unregistered_videos_prefix'
UNPROCESSED_VIDEOS_PREFIX_ENV_NAME = 's3_unprocessed_videos_prefix'


s3Client = boto3.client('s3')

video_types_to_extension = {
    'video/x-msvideo': 'avi',
    'video/mp4': 'mp4',
    'video/mpeg': 'mpeg',
    'video/ogg': 'ogv',
    'video/mp2t': 'ts',
    'video/webm': 'webm',
    'video/3gpp': '3gp',
    'video/3gpp2': '3g2'
}

# helpers
def object_type(obj: Dict) -> str:
    return obj['ResponseMetadata']['HTTPHeaders']['content-type']
    
    
def object_size_bytes(obj: Dict) -> int:
    return obj['ContentLength']

def get_object_meta(obj: Dict, id: str) -> Dict:
    meta = {
        'id': id,
        'type': object_type(obj),
        'size_in_bytes': object_size_bytes(obj)
    }
    return meta

def get_extension_by_content_type(content_type) -> str:
    return video_types_to_extension.get(content_type, None)

def is_video_type(content_type) -> bool:
    return get_extension_by_content_type(content_type) != None

def delete_object(bucket: str, key: str) -> None:
    try:
        print('deletes object')
        response = s3Client.delete_object(
            Bucket=bucket,
            Key=key
        )
        if response['ResponseMetadata']['HTTPStatusCode'] != 204:
            raise Exception('status code is not 204')
        print('response')
        print(response)
    except Exception as e:
        print('An exception occurred: failed to delete object')
        print(e)
        return

def get_signed_url(expires_in: int, bucket: str, key: str) -> str:
    return s3Client.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': key}, ExpiresIn=expires_in)

def get_video_duration_seconds(s3_source_signed_url: str) -> float:
    executable_path = f'{EXECUTABLES_DIRECTORY}/ffprobe'
    ffmpeg_cmd = f"{executable_path} \"" + str(s3_source_signed_url) + "\" -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1"
    print(ffmpeg_cmd)
    try:
        result = subprocess.run(shlex.split(ffmpeg_cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        duration = float(result.stdout)
    except Exception as e:
        print('Extract Duration exception')
        print(e)
        raise e
    return duration

def upload_frame_as_thumbnail(s3_source_signed_url: str, duration_seconds: float, bucket: str, thumbnail_key: str) -> None:
    executable_path = f'{EXECUTABLES_DIRECTORY}/ffmpeg'

    mid_of_video_duration_seconds = duration_seconds / 4
    time_frame_to_extract = str(datetime.timedelta(seconds=mid_of_video_duration_seconds)).split('.')[0] # hh:mm:ss
    frame_path = '/tmp/frame.png'
    
    ffmpeg_cmd = f"{executable_path} -y -ss {time_frame_to_extract} -i \"" + str(s3_source_signed_url) + f"\" -frames:v 1 {frame_path}"
    print(ffmpeg_cmd)
    try:
        os.system(ffmpeg_cmd)
    except Exception as e:
        print('Extract Thumbnail exception')
        print(e)
        raise e

    print('Going to upload thumbnail: ' + bucket + '/' + thumbnail_key)
    with open(frame_path, "rb") as f:
        resp = s3Client.put_object(Body=f, Bucket=bucket, Key=thumbnail_key, ACL=os.environ[S3_THUMBNAILS_ACL_ENV_NAME])
        print(resp)
        print('Thumbnail has been uploaded')

def resize_thumbnail(bucket: str, thumbnail_key: str, new_size = Tuple[int, int]) -> None:
    lambdaClient = boto3.client('lambda')
    try:
        response = lambdaClient.invoke(
            FunctionName=os.environ[IMAGE_RESIZER_LAMBDA_ARN_ENV_NAME],
            InvocationType='RequestResponse',
            Payload=json.dumps({
                    'source_file_key': thumbnail_key,
                    'dest_file_key': thumbnail_key,
                    'source_bucket': bucket,
                    'dest_bucket': bucket,
                    'new_size': list(new_size),
                    'ACL': os.environ[S3_THUMBNAILS_ACL_ENV_NAME]
                })
        )
        responseFromChild = json.load(response['Payload'])
    except Exception as e:
        print('Error during waiting for response from child')
        print(e)
        raise e
    print(responseFromChild)

def assert_necessery_env_are_here() -> None:
    for env in [IMAGE_RESIZER_LAMBDA_ARN_ENV_NAME, THUMBNAILS_PREFIX_ENV_NAME,
                UNREGISTERED_VIDEOS_PREFIX_ENV_NAME, UNPROCESSED_VIDEOS_PREFIX_ENV_NAME,
                S3_THUMBNAILS_ACL_ENV_NAME, S3_MAX_VIDEO_SIZE_IN_BYTES_ENV_NAME
            ]:
        if os.environ.get(env, None) is None:
            raise RuntimeError(f'missing env varialbe: {env}')

def send_sns(video_id: str, process_state: str, note: str) -> None:
    pass

def lambda_handler(event, context):
    assert_necessery_env_are_here()
    MAX_FILE_SIZE_IN_BYTES: int = int(float(os.environ[S3_MAX_VIDEO_SIZE_IN_BYTES_ENV_NAME]))
    SIGNED_URL_EXPIRATION: int = 60 * 10     # The number of seconds that the Signed URL is valid

    s3Ref = event['Records'][0]['s3']
    bucket = s3Ref['bucket']['name']
    key = s3Ref['object']['key']

    if key.split('/')[0] != os.environ[UNPROCESSED_VIDEOS_PREFIX_ENV_NAME]:
        print(f'An invalid s3 prefix, for key: {key}, processing has been stopped before being able to get video_id due to infrastructure failure')
        return {'statusCode': 500}

    try:
        obj: Dict = s3Client.get_object(
            Bucket=bucket,
            Key=key
        )
    except Exception as e:
        # internal error
        print('An exception occurred, internal error on get_object, processing has been stopped before being able to get video_id, infrastructure failure')
        print(e)
        raise e
    
    file_name: str = key.split('/')[-1]
    video_id: str = file_name.split('.')[0]
    
    try:
        meta = get_object_meta(obj, video_id)
        print(meta)
    except Exception as e:
        delete_object(bucket, key)
        print('An exception occurred, failed to get meta')
        print(e)
        send_sns(video_id, FAILED, CORRUPTED)
        return {'statusCode': 400}

    if MAX_FILE_SIZE_IN_BYTES < meta['size_in_bytes']:
        delete_object(bucket, key)
        send_sns(video_id, FAILED, MAX_FILE_SIZE_OVERFLOW)
        return {'statusCode': 400}
    
    if not is_video_type(meta['type']):
        print('not a video')
        # not a video, delete file!
        delete_object(bucket, key)
        send_sns(video_id, FAILED, NOT_A_VIDEO_TYPE)
    else:
        print('a video')
        # video
        try:
            # Generate a signed URL for the uploaded asset
            s3_source_signed_url: str = get_signed_url(SIGNED_URL_EXPIRATION, bucket, key)
        except Exception as e:
            delete_object(bucket, key)
            send_sns(video_id, FAILED, INTERNAL_ERROR_PLEASE_TRY_AGAIN_LATER)
            print('An exception occurred, internal error')
            print(e)
            raise e

        try:
            duration_seconds: float = get_video_duration_seconds(s3_source_signed_url)

            thumbnail_key = f'{os.environ[THUMBNAILS_PREFIX_ENV_NAME]}/{video_id}.png'
            upload_frame_as_thumbnail(s3_source_signed_url, duration_seconds, bucket, thumbnail_key)

            resize_thumbnail(bucket, thumbnail_key, THUMBNAIL_SIZE)
        except Exception as e:
            print('Video processing exception occurred')
            print(e)
            delete_object(bucket, key)
            send_sns(video_id, FAILED, CORRUPTED)
            raise e
    
    try:
        # move to unregistered S3 prefix
        copy_source = {'Bucket': bucket, 'Key': key}
        new_key = f'{os.environ[UNREGISTERED_VIDEOS_PREFIX_ENV_NAME]}/{file_name}'
        s3Client.copy(copy_source, bucket, new_key)
        delete_object(bucket, key) # not needed anymore
    except Exception as e:
        print('Exception, failed to move video into completed prefix')
        print(e)
        delete_object(bucket, key)
        send_sns(video_id, FAILED, INTERNAL_ERROR_PLEASE_TRY_AGAIN_LATER)
        raise e

    # create record in db
    user_id = 'UNKNOWN'
    record = {# todo: reformat it to the actual format dynamoDB accepts
        'hash_id': meta['id'],
        'video_type': meta['type'],
        'size_in_bytes': meta['size_in_bytes'],
        'duration_seconds': duration_seconds,
        'thumbnail_url': f'https://{bucket}.s3.amazonaws.com/{thumbnail_key}',
        'user_id': user_id,
        'upload_time': datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat(),
        'is_registered': False,
        'is_private': True,
        'Title': 'UNKNOWN',
        'Description': 'UNKOWN'
    }
    print(record)

    # notify waiting client
    send_sns(video_id, READY, AWAIT_FOR_REGISTRATION)

    return {
        'statusCode': 200,
        'body': json.dumps('Processing complete successfully')
    }

