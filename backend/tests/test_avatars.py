"""A reader's picture is redrawn, never kept as sent."""

from io import BytesIO

import pytest
from PIL import Image

from radar.avatars import AVATAR_SIZE, AvatarError, normalize


def _encoded(image: Image.Image, fmt: str, **options: object) -> bytes:
    out = BytesIO()
    image.save(out, fmt, **options)
    return out.getvalue()


def test_a_photo_becomes_a_small_square_without_its_metadata() -> None:
    photo = Image.new("RGB", (1200, 800), "navy")
    exif = photo.getexif()
    exif[0x0112] = 6  # shot rotated: the viewer must turn it
    exif[0x010F] = "Camera maker"  # anything a photo says about itself
    data = _encoded(photo, "JPEG", exif=exif.tobytes())

    result = Image.open(BytesIO(normalize(data)))

    assert result.format == "WEBP"
    assert result.size == (AVATAR_SIZE, AVATAR_SIZE)
    assert not result.getexif()


def test_transparency_survives() -> None:
    logo = Image.new("RGBA", (300, 300), (255, 0, 0, 0))

    result = Image.open(BytesIO(normalize(_encoded(logo, "PNG"))))

    assert result.mode == "RGBA"


@pytest.mark.parametrize(
    "data",
    [
        b"not a picture at all",
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
        # A tiny file that would decode to 36 megapixels.
        _encoded(Image.new("1", (6000, 6000)), "PNG"),
    ],
)
def test_what_is_not_a_reasonable_picture_is_refused(data: bytes) -> None:
    with pytest.raises(AvatarError):
        normalize(data)
