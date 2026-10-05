"""Supabase Storage helpers with local-disk support for development and tests."""

import os
from functools import lru_cache

from services.image_service import delete_image_file

BUCKET_NAME = os.environ.get('SUPABASE_STORAGE_BUCKET', 'odometer-photos')


def is_configured():
    return bool(os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_ROLE_KEY'))


@lru_cache(maxsize=1)
def _client():
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        raise RuntimeError('SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for photo storage.')
    from supabase import create_client

    return create_client(url, key)


def store_photo(filename, upload_folder):
    """Upload a processed JPEG to the private bucket, returning its object key."""
    if not is_configured():
        if os.environ.get('VERCEL') == '1':
            raise RuntimeError('Configure Supabase Storage environment variables before uploading photos.')
        return filename

    path = os.path.join(upload_folder, os.path.basename(filename))
    with open(path, 'rb') as image_file:
        _client().storage.from_(BUCKET_NAME).upload(
            filename,
            image_file.read(),
            {'content-type': 'image/jpeg', 'upsert': 'true'},
        )
    os.remove(path)
    return filename


def signed_photo_url(filename, expires_in=300):
    """Return a short-lived signed URL for an object in the private bucket."""
    response = _client().storage.from_(BUCKET_NAME).create_signed_url(filename, expires_in)
    data = response if isinstance(response, dict) else response.model_dump()
    signed_url = data.get('signedURL') or data.get('signedUrl')
    if not signed_url:
        raise RuntimeError('Supabase did not return a signed URL for the requested photo.')
    return signed_url


def delete_photos(filenames, upload_folder):
    """Delete photo objects from Supabase, or local files during development."""
    names = list(dict.fromkeys(os.path.basename(name) for name in filenames if name))
    if not names:
        return
    if is_configured():
        bucket = _client().storage.from_(BUCKET_NAME)
        for offset in range(0, len(names), 100):
            bucket.remove(names[offset:offset + 100])
        return
    if os.environ.get('VERCEL') == '1':
        raise RuntimeError('Configure Supabase Storage before deleting photos on Vercel.')
    for name in names:
        delete_image_file(name, upload_folder=upload_folder)
