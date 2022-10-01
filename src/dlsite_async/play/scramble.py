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
from pathlib import Path
from random import Random
from typing import Any, Union

from .models import PlayFile


logger = logging.getLogger(__name__)


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


def descramble(path: Union[str, Path], playfile: PlayFile) -> None:
    """Descramble the specified image file.

    Args:
        path: Image file path.
        playfile: Original image PlayFile.
    """
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover
        logger.warn("Image descramble requires installation with dlsite-async[pil]")
        return

    with Image.open(path) as im:
        tile_w = 128
        optimized = playfile.files["optimized"]
        width = optimized["width"]
        height = optimized["height"]
        tiles_w = math.ceil(width / tile_w)
        tiles_h = math.ceil(height / tile_w)
        tiles = [
            im.crop(
                (
                    x * tile_w,
                    y * tile_w,
                    (x + 1) * tile_w,
                    (y + 1) * tile_w,
                )
            )
            for y in range(tiles_h)
            for x in range(tiles_w)
        ]
        new_im = im.copy()

    seed = int(playfile.optimized_name[5:12], 16)
    shuffle = {}
    # tile order is reverse mapping MT prng output {<val>: index}
    for v, k in enumerate(_mt_tiles(seed, len(tiles))):
        shuffle[k] = v
    for i in range(len(tiles)):
        tile = tiles[shuffle[i]]
        x = i % tiles_w
        y = i // tiles_w
        new_im.paste(tile, (x * tile_w, y * tile_w))
    # crop to actual image dimensions
    # (scrambled image is padded to align to 128 pixel tile boundary)
    new_im.crop((0, 0, width, height))
    new_im.save(path)
