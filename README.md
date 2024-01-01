# DLsite Async

[![PyPI](https://img.shields.io/pypi/v/dlsite-async.svg)][pypi status]
[![Status](https://img.shields.io/pypi/status/dlsite-async.svg)][pypi status]
[![Python Version](https://img.shields.io/pypi/pyversions/dlsite-async)][pypi status]
[![License](https://img.shields.io/pypi/l/dlsite-async)][license]

[![Read the documentation at https://dlsite-async.readthedocs.io/](https://img.shields.io/readthedocs/dlsite-async/latest.svg?label=Read%20the%20Docs)][read the docs]
[![Tests](https://github.com/bhrevol/dlsite-async/workflows/Tests/badge.svg)][tests]
[![Codecov](https://codecov.io/gh/bhrevol/dlsite-async/branch/main/graph/badge.svg)][codecov]

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)][pre-commit]
[![Black](https://img.shields.io/badge/code%20style-black-000000.svg)][black]

[pypi status]: https://pypi.org/project/dlsite-async/
[read the docs]: https://dlsite-async.readthedocs.io/
[tests]: https://github.com/bhrevol/dlsite-async/actions?workflow=Tests
[codecov]: https://app.codecov.io/gh/bhrevol/dlsite-async
[pre-commit]: https://github.com/pre-commit/pre-commit
[black]: https://github.com/psf/black

## Features

- Async DLsite API for fetching work metadata
- Supports most DLsite sites:
  - Comipo (`comic`)
  - Doujin (All-ages/`home`, Adult/`maniax`)
  - Adult comics (`books`)
  - All-ages games (`soft`)
  - Galge (`pro`)
  - Apps (`appx`)
- Supports common metadata for most DLsite work types
- Japanese and English locale support
  (English metadata may not be available for all works)

- Async DLsite Play API
- Supports downloading web-optimized versions of works from DLsite Play
  - Downloads require valid DLsite account login (only purchased works can be
    downloaded)
  - Only `optimized` file versions can be downloaded
  - Images may be resized to smaller resolution and compressed
  - Audio files may be re-encoded and compressed into MP3 format
  - Video files may be resized to smaller resolution and re-encoded
  - Play API returns an m3u8 HLS stream playlist for videos. Downloading the
    HLS video segments is not supported.
- Supports de-scrambling downloaded images (from book type works)
  - Image de-scrambling requires installation with `dlsite-async[pil]`

## Requirements

- Python 3.9+

## Installation

You can install _DLsite Async_ via [pip] from [PyPI]:

```console
$ pip install dlsite-async
```

Certain features require may installing extra dependencies:

```console
$ pip install dlsite-async[pil]
```

## Usage examples

Fetch manga information:

```py
>>> import asyncio
>>> from dlsite_async import DlsiteAPI
>>> async def f():
...     async with DlsiteAPI() as api:
...         return await api.get_work("BJ370220")
...
>>> asyncio.run(f())
Work(
    product_id='BJ370220',
    site_id='comic',
    maker_id='BG01675',
    work_name='衛宮さんちの今 日のごはん (6)\u3000レシピ本付特装版',
    age_category=<AgeCategory.ALL_AGES: 1>,
    circle=None,
    brand=None,
    publisher='KADOKAWA',
    work_image='//img.dlsite.jp/.../BJ370220_img_main.jpg',
    regist_date=datetime.datetime(2021, 10, 28, 0, 0),
    work_type=<WorkType.MANGA: 'MNG'>,
    book_type=<BookType.BOOK: 'comic'>,
    ...
    author=['TAa', '只野まこと', 'ＴＹＰＥ−ＭＯＯＮ'],
    ...
    genre=['少年コミック', 'ギャグ', 'コメディ', 'ほのぼの'],
    label='KADOKAWA',
    ...
    page_count=307
)
```

Fetch English voice/ASMR information:

```py
>>> async def f():
...     async with DlsiteAPI(locale="en_US") as api:
...         return await api.get_work("RJ294126")
...
>>> asyncio.run(f())
Work(
    product_id='RJ294126',
    site_id='maniax',
    maker_id='RG51931',
    work_name='Pure Pussy on Duty',
    age_category=<AgeCategory.R18: 3>,
    circle='aoharu fetishism',
    brand=None,
    publisher=None,
    work_image='//img.dlsite.jp/.../RJ294126_img_main.jpg',
    regist_date=datetime.datetime(2020, 8, 30, 0, 0),
    work_type=<WorkType.VOICE_ASMR: 'SOU'>,
    ...
    illustration=['ぬこぷし'],
    voice_actor=['逢坂成美'],
    ...
    genre=['Healing', 'Dirty Talk', 'Binaural', 'ASMR', ...],
    ...
    file_format=['WAV'],
    file_size='Total 010.63GB',
    ...
)
```

List DLsite Play files in a work:

```py
>>> from dlsite_async import PlayAPI
>>> async def f():
...     async with PlayAPI() as play_api:
...         await play_api.login("username", "password")
...         token = await play_api.download_token("RJ294126")
...         tree = await play_api.ziptree(token)
...         return dict(tree.items())
...
>>> asyncio.run(f())
{
    '純愛おま○こ当番【アップデート版】/readme.txt': PlayFile(
        length=4006,
        type='text',
        files={
            'optimized': {
                'encoding': 'UTF-8',
                'length': 5232,
                'name': '95b8dd8e45a2ff0b1d45717b93a096b7.txt',
                'size': '5.1KB'
            }
        }
    ),
    ...,
    '純愛おま○こ当番【アップデート版】/02_wav/track00_タイトルコール.wav' PlayFile(
        length=5193978,
        type='audio',
        files={
            'optimized': {
                'bit_rate': 74182,
                'duration': 6.768,
                'length': 62758,
                'name': '069498e95c11ad47fc65ee87a1a0ae60.mp3',
                'size': '61.3KB'
            }
        }
    ),
    ...,
    '純愛おま○こ当番【アップデート版】/04_omake/01：高画質画像/junai_r_01.jpg': PlayFile(
        length=1394068,
        type='image',
        files={
            'files': {
                'crypt': False,
                'height': 3000,
                'length': 1394068,
                'name': 'd0b8bc7a93e4f1c4c3d5e3eed6d65393.jpg',
                'size': '1.3MB',
                'width': 2143
            },
            'optimized': {
                'crypt': True,
                'height': 1280,
                'length': 220746,
                'name': 'd0b8bc7a93e4f1c4c3d5e3eed6d65393.jpg',
                'size': '215.6KB',
                'width': 914
            }
        }
    ),
    ...,
    '純愛おま○こ当番【アップデート版】/05_字幕付き音声動画/trackEX_おま○こ当番と体育倉庫でナイショえっち.mp4': PlayFile(
        length=297495132,
        type='video',
        files={
            'files': {
                'frame_rate': '24/1',
                'height': 1080,
                'width': 1920
            },
            'optimized': {
                'duration': '1004.693333',
                'name': 'd5e47f10d9d98944f6d4003497087c53.m3u8',
                'streams': ['v720p', 'v480p', 'v240p']
            }
        }
    ),
    ...,
}
```

Download web-optimized images from a manga/comic work to the current working directory
(Note that using `descramble=True` requires `dlsite_async[pil]`):

```py
>>> import os
>>> import asyncio
>>> from dlsite_async import PlayAPI
>>> async def f():
...     async with PlayAPI() as play_api:
...         await play_api.login(username, password)
...         token = await play_api.download_token("BJ277832")
...         tree = await play_api.ziptree(token)
...         for filename, playfile in tree.items():
...             if playfile.type != "image":
...                 continue
...             orig_path, _ = os.path.splitext(filename)
...             _, ext = os.path.splitext(playfile.optimized_name)
...             dest = f"{orig_path}{ext}"
...             await play_api.download_playfile(
...                 token, playfile, dest, mkdir=True, descramble=True
...             )
...
>>> asyncio.run(f())
```

## Contributing

Contributions are very welcome.
To learn more, see the [Contributor Guide].

## License

Distributed under the terms of the [MIT license][license],
_DLsite Async_ is free and open source software.

## Issues

If you encounter any problems,
please [file an issue] along with a detailed description.

## Credits

This project was generated from [@cjolowicz]'s [Hypermodern Python Cookiecutter] template.

[@cjolowicz]: https://github.com/cjolowicz
[pypi]: https://pypi.org/
[hypermodern python cookiecutter]: https://github.com/cjolowicz/cookiecutter-hypermodern-python
[file an issue]: https://github.com/bhrevol/dlsite-async/issues
[pip]: https://pip.pypa.io/

<!-- github-only -->

[license]: https://github.com/bhrevol/dlsite-async/blob/main/LICENSE
[contributor guide]: https://github.com/bhrevol/dlsite-async/blob/main/CONTRIBUTING.md
[command-line reference]: https://dlsite-async.readthedocs.io/en/latest/usage.html
