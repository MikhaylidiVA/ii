"""
MinIO/S3 клиент для хранения файлов
"""
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings


# Создание S3 клиента
s3_client = boto3.client(
    's3',
    endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
    aws_access_key_id=settings.MINIO_ACCESS_KEY,
    aws_secret_access_key=settings.MINIO_SECRET_KEY,
    config=boto3.session.Config(signature_version='s3v4'),
)


def ensure_bucket_exists():
    """Создание бакета если не существует"""
    try:
        s3_client.head_bucket(Bucket=settings.MINIO_BUCKET)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            s3_client.create_bucket(Bucket=settings.MINIO_BUCKET)
            print(f"Bucket '{settings.MINIO_BUCKET}' created")
        else:
            raise


def upload_file(file_path: str, object_name: str, bucket: str = None) -> bool:
    """
    Загрузка файла в S3
    
    Args:
        file_path: Путь к файлу на диске
        object_name: Имя объекта в S3
        bucket: Имя бакета (по умолчанию из конфига)
    
    Returns:
        True если успешно, False если ошибка
    """
    if bucket is None:
        bucket = settings.MINIO_BUCKET
    
    try:
        s3_client.upload_file(file_path, bucket, object_name)
        return True
    except ClientError as e:
        print(f"Error uploading file: {e}")
        return False


def upload_file_bytes(file_bytes: bytes, object_name: str, bucket: str = None, content_type: str = "application/octet-stream") -> bool:
    """
    Загрузка файла из байтов в S3
    
    Args:
        file_bytes: Байты файла
        object_name: Имя объекта в S3
        bucket: Имя бакета
        content_type: MIME тип контента
    
    Returns:
        True если успешно
    """
    if bucket is None:
        bucket = settings.MINIO_BUCKET
    
    try:
        from io import BytesIO
        s3_client.upload_fileobj(
            BytesIO(file_bytes),
            bucket,
            object_name,
            ExtraArgs={'ContentType': content_type},
        )
        return True
    except ClientError as e:
        print(f"Error uploading file bytes: {e}")
        return False


def download_file(object_name: str, file_path: str, bucket: str = None) -> bool:
    """Скачивание файла из S3"""
    if bucket is None:
        bucket = settings.MINIO_BUCKET
    
    try:
        s3_client.download_file(bucket, object_name, file_path)
        return True
    except ClientError as e:
        print(f"Error downloading file: {e}")
        return False


def get_file_bytes(object_name: str, bucket: str = None) -> bytes | None:
    """Получение файла как байты"""
    if bucket is None:
        bucket = settings.MINIO_BUCKET
    
    try:
        response = s3_client.get_object(Bucket=bucket, Key=object_name)
        return response['Body'].read()
    except ClientError as e:
        print(f"Error getting file: {e}")
        return None


def delete_file(object_name: str, bucket: str = None) -> bool:
    """Удаление файла из S3"""
    if bucket is None:
        bucket = settings.MINIO_BUCKET
    
    try:
        s3_client.delete_object(Bucket=bucket, Key=object_name)
        return True
    except ClientError as e:
        print(f"Error deleting file: {e}")
        return False


def delete_files(object_names: list[str], bucket: str = None) -> int:
    """Пакетное удаление файлов"""
    if bucket is None:
        bucket = settings.MINIO_BUCKET
    
    if not object_names:
        return 0
    
    try:
        objects_to_delete = [{'Key': name} for name in object_names]
        response = s3_client.delete_objects(
            Bucket=bucket,
            Delete={'Objects': objects_to_delete}
        )
        return len(response.get('Deleted', []))
    except ClientError as e:
        print(f"Error deleting files: {e}")
        return 0


def generate_presigned_url(object_name: str, expiration: int = 3600, bucket: str = None) -> str | None:
    """Генерация временной ссылки на файл"""
    if bucket is None:
        bucket = settings.MINIO_BUCKET
    
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': object_name},
            ExpiresIn=expiration,
        )
        return url
    except ClientError as e:
        print(f"Error generating presigned URL: {e}")
        return None


def list_files(prefix: str = "", bucket: str = None) -> list[str]:
    """Список файлов в бакете по префиксу"""
    if bucket is None:
        bucket = settings.MINIO_BUCKET
    
    try:
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        if 'Contents' in response:
            return [obj['Key'] for obj in response['Contents']]
        return []
    except ClientError as e:
        print(f"Error listing files: {e}")
        return []
