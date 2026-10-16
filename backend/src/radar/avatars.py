"""A reader's picture: a common image in, a small square WebP out.

The upload is decoded and drawn anew, never stored as sent: what comes out
has no EXIF (no location, no camera), no second payload glued to the file,
and a size fit for a database row. Without a photo the reader has one of
the ready pictures.
"""

import secrets
import uuid
from io import BytesIO
from typing import Literal, get_args

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


LOGO_SIZE = 512


def normalize_logo(data: bytes) -> bytes:
    """A company's logo as a WebP no larger than LOGO_SIZE on its long side,
    in its own proportions: a wide logo is not cropped to a square."""
    return _redraw(data, square=False)


def normalize(data: bytes) -> bytes:
    """A square AVATAR_SIZE WebP of the picture, cropped around its centre."""
    return _redraw(data, square=True)


def _redraw(data: bytes, *, square: bool) -> bytes:
    size = AVATAR_SIZE if square else LOGO_SIZE
    try:
        with Image.open(BytesIO(data), formats=FORMATS) as source:
            width, height = source.size
            if width * height > MAX_PIXELS:
                raise AvatarError("Картинка больше 16 мегапикселей, уменьшите её.")
            # A GIF gives its first frame; a photo is turned the way it was shot.
            source.seek(0)
            # A JPEG decodes straight at a fraction of its size: a 16 MP photo
            # never takes its full 50 MB in memory.
            source.draft("RGB", (size * 2, size * 2))
            image = ImageOps.exif_transpose(source)
            image = image.convert("RGBA" if image.has_transparency_data else "RGB")
            if square:
                image = ImageOps.fit(image, (size, size), Image.Resampling.LANCZOS)
            else:
                image.thumbnail((size, size), Image.Resampling.LANCZOS)
            out = BytesIO()
            image.save(out, "WEBP", quality=QUALITY, method=4)
            return out.getvalue()
    except AvatarError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise AvatarError("Подходят картинки JPEG, PNG, WebP и GIF.") from exc


# The ready pictures a reader may pick instead of a photo: fluffy balls of
# nine colours, served by the web app from /brand/avatars/<name>.webp.
AvatarPreset = Literal["green", "blue", "yellow", "orange", "teal", "purple", "red", "sky", "grey"]
AVATAR_PRESETS: tuple[AvatarPreset, ...] = get_args(AvatarPreset)


def random_preset() -> AvatarPreset:
    """A picture for a new account, so that two new readers look apart."""
    return secrets.choice(AVATAR_PRESETS)


def preset_for(user_id: uuid.UUID, stored: str | None) -> AvatarPreset:
    """The reader's own pick, or one of the nine derived from the account id:
    an account from before the pictures existed keeps the same one everywhere."""
    for preset in AVATAR_PRESETS:
        if preset == stored:
            return preset
    return AVATAR_PRESETS[user_id.int % len(AVATAR_PRESETS)]
