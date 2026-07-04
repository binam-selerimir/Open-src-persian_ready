import uuid
from pathlib import Path

import magic
from PIL import Image
from django.core.files.storage import default_storage

from .sanitization import ALLOWED_INLINE_EXTENSIONS

MAX_INLINE_MEDIA_BYTES = {
    'image': 10 * 1024 * 1024,
    'audio': 25 * 1024 * 1024,
    'video': 50 * 1024 * 1024,
}

ALLOWED_MIME_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/ogg',
    'audio/mp4', 'audio/aac', 'audio/flac',
    'video/mp4', 'video/webm', 'video/quicktime', 'video/ogg', 'video/x-matroska',
}

MIME_BUFFER_SIZE = 4096

EXPECTED_MIME_PREFIX = {
    'image': 'image/',
    'audio': 'audio/',
    'video': 'video/',
}


def detect_mime(uploaded_file):
    try:
        return magic.from_buffer(uploaded_file.read(MIME_BUFFER_SIZE), mime=True)
    except Exception:
        return None
    finally:
        uploaded_file.seek(0)


def classify_upload_file(filename):
    ext = Path(filename).suffix.lower()
    for kind, extensions in ALLOWED_INLINE_EXTENSIONS.items():
        if ext in extensions:
            return kind
    return None


def validate_inline_upload(uploaded_file):
    kind = classify_upload_file(uploaded_file.name)
    if not kind:
        return None, 'Unsupported file type.'

    max_bytes = MAX_INLINE_MEDIA_BYTES[kind]
    if uploaded_file.size > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        return None, f'File too large (max {max_mb} MB for {kind}).'

    mime = detect_mime(uploaded_file)
    if mime is None:
        return None, 'Unable to determine file type.'
    if mime not in ALLOWED_MIME_TYPES:
        return None, f'Invalid media type ({mime}).'
    if not mime.startswith(EXPECTED_MIME_PREFIX[kind]):
        return None, f'File extension does not match content ({mime}).'

    if kind == 'image':
        try:
            image = Image.open(uploaded_file)
            image.verify()
        except Exception:
            return None, 'Corrupted or invalid image.'
        uploaded_file.seek(0)

    return kind, None


def save_inline_media(uploaded_file):
    kind, error = validate_inline_upload(uploaded_file)
    if error:
        return None, error

    ext = Path(uploaded_file.name).suffix.lower()
    filename = f'{uuid.uuid4().hex}{ext}'
    path = default_storage.save(f'posts/inline/{filename}', uploaded_file)
    return default_storage.url(path), None
