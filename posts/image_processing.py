"""
posts/image_processing.py
==========================
Image pre-processing pipeline applied to uploaded images.

process_cover_image() performs three operations on the uploaded file:
  1. Loads and validates the image through Pillow — catches corrupted files early.
  2. Converts to RGB (flattening transparency) so the result is always JPEG-safe.
  3. Centre-crops to the target 16:9 aspect ratio, then resizes to 1200×675 px.
  4. Saves as JPEG at quality 85 with optimise=True (progressive JPEG).

process_avatar_image() shares the same loading/validation/RGB pipeline but
centre-crops to a 1:1 square and resizes to AVATAR_SIZE x AVATAR_SIZE — the
right shape for profile pictures, which process_cover_image() (16:9,
1200x675) is not.

Security
--------
Image.MAX_IMAGE_PIXELS is set to ~178 MP to guard against decompression-bomb
attacks (images with tiny file sizes that expand to gigabytes in memory).
Pillow raises DecompressionBombError if the decoded pixel count exceeds this limit.
"""

from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError

# Guard against decompression bomb attacks: refuse images whose uncompressed
# pixel count exceeds this limit (~178 MP — well above real use cases).
Image.MAX_IMAGE_PIXELS = 178_956_970

# Target dimensions for all cover images: 1200 × 675 (standard 16:9).
COVER_WIDTH = 1200
COVER_HEIGHT = 675
COVER_QUALITY = 85                        # JPEG quality: good balance of size vs clarity.
COVER_RATIO = COVER_WIDTH / COVER_HEIGHT  # ≈ 1.7778  (16:9)

# Target dimensions for avatars: a square crop, much smaller than a cover
# image since avatars are displayed at small sizes (panel header, profile
# cards, etc.).
AVATAR_SIZE = 512
AVATAR_QUALITY = 85
AVATAR_RATIO = 1.0  # 1:1 square


def _center_crop_to_ratio(img, target_ratio):
    """
    Centre-crop an image to the given width/height ratio without stretching.

    If the source is wider than the target ratio, crop the sides.
    If the source is taller, crop the top and bottom.
    The cropped region is always centred on the original image.
    """
    src_ratio = img.width / max(img.height, 1)
    if src_ratio > target_ratio:
        # Source is too wide: trim equal amounts from left and right.
        new_width = int(img.height * target_ratio)
        left = (img.width - new_width) // 2
        return img.crop((left, 0, left + new_width, img.height))
    # Source is too tall: trim equal amounts from top and bottom.
    new_height = int(img.width / target_ratio)
    top = (img.height - new_height) // 2
    return img.crop((0, top, img.width, top + new_height))


def _to_rgb(img):
    """
    Flatten any transparent or paletted image to an RGB JPEG-safe image.

    JPEG does not support transparency; pasting an RGBA image onto a white
    background is the standard way to composite it before saving as JPEG.
    Paletted ('P' mode) images are converted to RGBA first to preserve
    any transparency in the palette before compositing.
    """
    if img.mode == 'P':
        # Convert palette to RGBA so we can access the transparency channel.
        img = img.convert('RGBA')
    if img.mode in ('RGBA', 'LA'):
        # Composite transparent pixels onto a white background.
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])   # Use alpha channel as mask.
        return background
    return img.convert('RGB')


def _open_image(uploaded_file):
    """
    Decode and fully load an uploaded file as a Pillow Image.

    img.load() forces full decoding here; without it Pillow lazily loads
    pixel data and some corruption is only detected later (e.g. when
    resizing), which would surface as a confusing error far from the
    upload code.

    Raises
    ------
    ValueError : if the file cannot be decoded as an image.
    """
    try:
        img = Image.open(uploaded_file)
        img.load()
    except (UnidentifiedImageError, OSError, Exception) as exc:
        raise ValueError('Invalid image file.') from exc
    from PIL import ImageOps
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    return img


def process_cover_image(uploaded_file):
    """
    Resize and centre-crop a cover upload to fixed 16:9 dimensions.

    Parameters
    ----------
    uploaded_file : Django InMemoryUploadedFile or TemporaryUploadedFile

    Returns
    -------
    ContentFile : a Django ContentFile wrapping the processed JPEG bytes,
                  named '<original_stem>.jpg'.

    Raises
    ------
    ValueError : if the file cannot be decoded as an image.
    """
    img = _open_image(uploaded_file)

    img = _to_rgb(img)
    img = _center_crop_to_ratio(img, COVER_RATIO)
    img = img.resize((COVER_WIDTH, COVER_HEIGHT), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    # optimize=True enables multi-pass Huffman table optimisation; negligible
    # CPU cost for a measurable (~5%) reduction in file size.
    img.save(buffer, format='JPEG', quality=COVER_QUALITY, optimize=True)
    buffer.seek(0)

    # Preserve the original file stem but force the .jpg extension.
    stem = Path(uploaded_file.name).stem or 'cover'
    return ContentFile(buffer.read(), name=f'{stem}.jpg')


def process_avatar_image(uploaded_file):
    """
    Resize and centre-crop an avatar upload to a fixed square.

    Unlike process_cover_image() (16:9, 1200x675 — designed for wide post
    cover banners), this centre-crops to a 1:1 square and resizes to
    AVATAR_SIZE x AVATAR_SIZE, which is the correct shape for a profile
    picture shown in circular/square avatar slots across the site.

    Parameters
    ----------
    uploaded_file : Django InMemoryUploadedFile or TemporaryUploadedFile

    Returns
    -------
    ContentFile : a Django ContentFile wrapping the processed JPEG bytes,
                  named '<original_stem>.jpg'.

    Raises
    ------
    ValueError : if the file cannot be decoded as an image.
    """
    img = _open_image(uploaded_file)

    img = _to_rgb(img)
    img = _center_crop_to_ratio(img, AVATAR_RATIO)
    img = img.resize((AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=AVATAR_QUALITY, optimize=True)
    buffer.seek(0)

    stem = Path(uploaded_file.name).stem or 'avatar'
    return ContentFile(buffer.read(), name=f'{stem}.jpg')
