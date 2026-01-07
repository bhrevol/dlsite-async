"""DLsite Play image scrambling tests."""
from pathlib import Path

from PIL import Image

from dlsite_async.play.models import PlayFile
from dlsite_async.play.scramble import descramble


def test_descramble_crops_to_original_size(tmp_path: Path) -> None:
    """Image should be cropped to original dimensions after descramble.

    When original image dimensions are not aligned to 128px tile boundary,
    DLsite pads the image with white pixels. After descramble, the image
    should be cropped back to original dimensions.

    Test case:
        - Original image: 200x160 (not divisible by 128)
        - Padded image: 256x256 (2x2 tiles)
        - After descramble: should be 200x160 (cropped)
    """
    # Create a 256x256 padded image (simulating DLsite's padding)
    image_file = tmp_path / "test_crop.png"
    im = Image.new("RGB", (256, 256), color=(255, 255, 255))  # White padding
    # Fill actual content area (200x160) with red
    content = Image.new("RGB", (200, 160), color=(255, 0, 0))
    im.paste(content, (0, 0))
    im.save(image_file)

    playfile = PlayFile(
        1,
        "image",
        {
            "optimized": {
                "name": "000000000000.png",
                "length": 1,
                "width": 200,  # Original width (before padding)
                "height": 160,  # Original height (before padding)
                "crypt": False,  # No scrambling for this test
            }
        },
        "abc123",
    )
    descramble(image_file, playfile)

    with Image.open(image_file) as result:
        # Image should be cropped to original dimensions
        assert result.size == (200, 160), f"Expected (200, 160), got {result.size}"
        # All pixels should be red (content), no white padding
        px = result.load()
        assert px
        assert px[199, 159] == (255, 0, 0), "Bottom-right should be red content"


def test_descramble(tmp_path: Path) -> None:
    """Image should be descrambled.

    Descrambles 2x2 tiled image with known seed (0).
    Scrambled image is in format:
        black, red
        green, blue
    Descrambled image should be:
        black, green
        red, blue

    Note:
        DLsite optimized images are always jpg but we use png here so tiles
        do not get mangled/blended by jpg compression on save().
    """
    image_file = tmp_path / "test.png"
    im = Image.new("RGB", (256, 256))
    im.paste(Image.new("RGB", (128, 128), color=(255, 0, 0)), (0, 128))
    im.paste(Image.new("RGB", (128, 128), color=(0, 255, 0)), (128, 0))
    im.paste(Image.new("RGB", (128, 128), color=(0, 0, 255)), (128, 128))
    im.save(image_file)
    playfile = PlayFile(
        1,
        "image",
        {
            "optimized": {
                "name": "000000000000.png",
                "length": 1,
                "width": 256,
                "height": 256,
            }
        },
        "abc123",
    )
    descramble(image_file, playfile)
    with Image.open(image_file) as im:
        px = im.load()
        assert px
        assert px[0, 0] == (0, 0, 0)
        assert px[0, 128] == (0, 0, 255)
        assert px[128, 0] == (255, 0, 0)
        assert px[128, 128] == (0, 255, 0)
