"""DLsite Play image scrambling module.

DLsite play ``crypt`` function slices image into 128x128px tiles and then
shuffles them so that any image retrieved from the web server appears
scrambled. Restoring the original image requires putting the tiles back into
the correct order.

Images are shuffled using a Mersenne Twister PRNG with a known seed (see
image viewer ``main.js``).
"""

import logging
import math
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import PlayFile


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScrambleTile:
    """Scrambled image tile.

    Attributes:
        width: Tile width in pixels.
        height: Tile height in pixels.
        scramble_x: x-coordinate of the tile in the scrambled image.
        scramble_y: y-coordinate of the tile in the scrambled image.
        original_x: x-coordinate of the tile in the original image.
        original_y: y-coordinate of the tile in the original image.
    """

    width: int
    height: int
    scramble_x: int
    scramble_y: int
    original_x: int
    original_y: int


@dataclass(frozen=True)
class ScrambleInfo:
    """Scrambled image tileset information.

    Attributes:
        width: Original (descrambled) image width in pixels.
        height: Original (descrambled) image height in pixels.
        tiles: List of scrambled image tiles. Tile order is not guaranteed
            and depends on the scramble method.

    Note:
        Scrambled image dimensions are aligned to tile dimensions. After
        descrambling tiles, the resulting image should be cropped to
        the original image width and height to remove padding.
    """

    width: int
    height: int
    tiles: list[ScrambleTile]


class _MTRandom(Random):
    """DLsite Play image viewer Mersenne Twister (MT19937) implementation.

    Python ``random`` uses MT19937, but with additional seed manipulation.
    We only want the reference Knuth seed step (``init_genrand`` in CPython
    ``_randommodule.c``)
    """

    N = 624

    def seed(self, a: int = 0, **kwargs: Any) -> None:  # type: ignore[override]
        """Seed the PRNG."""
        mt = [a & 0xFFFFFFFF] * self.N
        for i in range(1, self.N):
            mt[i] = 1812433253 * (mt[i - 1] ^ (mt[i - 1] >> 30)) + i
            mt[i] &= 0xFFFFFFFF
        state = tuple(mt) + (self.N,)
        self.setstate((self.VERSION, state, None))


def _mt_tiles(seed: int, length: int) -> list[int]:
    """Return Mersenne Twister array."""
    if length > 624:  # pragma: no cover
        raise ValueError
    rs = _MTRandom(seed)
    a = list(range(length))
    pos = 0
    for n in range(length - 1, -1, -1):
        e = math.floor(rs.random() * (n + 1))
        r = a[n]
        a[n] = a[e]
        a[e] = r

        # (partially) adjust for dlsite's MT implementation
        #
        # we don't care about accounting for the MT array twist because
        # we will never actually have >624 iterations
        pos += 1
        version, state, next_gauss = rs.getstate()
        state = state[:-1] + (pos,)
        rs.setstate((version, state, next_gauss))
    return a


def descramble_tiles(seed: int, width: int, height: int) -> Iterator[ScrambleTile]:
    """Yield tiles for a scrambled image with the specified seed and dimensions."""
    tile_w = 128
    tiles_w = math.ceil(width / tile_w)
    tiles_h = math.ceil(height / tile_w)
    tiles = [(x * tile_w, y * tile_w) for y in range(tiles_h) for x in range(tiles_w)]
    shuffle = {}
    # tile order is reverse mapping MT prng output {<val>: index}
    for v, k in enumerate(_mt_tiles(seed, len(tiles))):
        shuffle[k] = v
    for i in range(len(tiles)):
        scramble_x, scramble_y = tiles[shuffle[i]]
        yield ScrambleTile(
            width=tile_w,
            height=tile_w,
            scramble_x=scramble_x,
            scramble_y=scramble_y,
            original_x=(i % tiles_w) * tile_w,
            original_y=(i // tiles_w) * tile_w,
        )


def descramble(path: str | Path, playfile: "PlayFile", **save_kwargs: Any) -> None:
    """Descramble the specified image file.

    Args:
        path: Image file path.
        playfile: Original image PlayFile.
        save_kwargs: Additional arguments to be passed into Pillow ``Image.save()``.
    """
    if not playfile.scramble_info:
        return

    try:
        from PIL import Image
    except ImportError:  # pragma: no cover
        logger.warning("Image descramble requires installation with dlsite-async[pil]")
        return

    path = Path(path)
    with Image.open(path) as im:
        new_im = im.copy()
        for tile in playfile.scramble_info.tiles:
            tile_im = im.crop(
                (
                    tile.scramble_x,
                    tile.scramble_y,
                    tile.scramble_x + tile.width,
                    tile.scramble_y + tile.height,
                )
            )
            new_im.paste(tile_im, (tile.original_x, tile.original_y))
    # crop to actual image dimensions
    # (scrambled image is padded to align to 128 pixel tile boundary)
    new_im = new_im.crop(
        (0, 0, playfile.scramble_info.width, playfile.scramble_info.height)
    )
    if path.suffix.lower() in (".jpg", ".jpeg") and "quality" not in save_kwargs:
        save_kwargs["quality"] = "keep" if new_im.format == "JPEG" else 95
    new_im.save(path, **save_kwargs)
