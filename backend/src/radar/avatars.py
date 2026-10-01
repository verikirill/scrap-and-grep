"""A reader's picture: a common image in, a small square WebP out.

The upload is decoded and drawn anew, never stored as sent: what comes out
has no EXIF (no location, no camera), no second payload glued to the file,
and a size fit for a database row.
"""

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

AVATAR_SIZE = 256
MAX_BYTES = 5_000_000
# A 10 000 x 10 000 PNG compresses to kilobytes and decodes to hundreds of
# megabytes: the size is checked from the header, before any decoding.
MAX_PIXELS = 16_000_000
FORMATS = ("JPEG", "PNG", "WEBP", "GIF")
QUALITY = 85


class AvatarError(ValueError):
    """The upload is not a picture this service takes."""


def normalize(data: bytes) -> bytes:
    """A square AVATAR_SIZE WebP of the picture, cropped around its centre."""
    try:
        with Image.open(BytesIO(data), formats=FORMATS) as source:
            width, height = source.size
            if width * height > MAX_PIXELS:
                raise AvatarError("Картинка больше 16 мегапикселей, уменьшите её.")
            # A GIF gives its first frame; a photo is turned the way it was shot.
            source.seek(0)
            # A JPEG decodes straight at a fraction of its size: a 16 MP photo
            # never takes its full 50 MB in memory.
            source.draft("RGB", (AVATAR_SIZE * 2, AVATAR_SIZE * 2))
            image = ImageOps.exif_transpose(source)
            image = image.convert("RGBA" if image.has_transparency_data else "RGB")
            square = ImageOps.fit(image, (AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)
            out = BytesIO()
            square.save(out, "WEBP", quality=QUALITY, method=4)
            return out.getvalue()
    except AvatarError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise AvatarError("Подходят картинки JPEG, PNG, WebP и GIF.") from exc
