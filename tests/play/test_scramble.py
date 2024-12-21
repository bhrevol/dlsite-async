"""DLsite Play image scrambling tests."""
from pathlib import Path

from PIL import Image

from dlsite_async.play.models import PlayFile
from dlsite_async.play.scramble import descramble


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
