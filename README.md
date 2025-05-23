# Stereo4D-VR180 Downloader

A tiny utility for bulk-downloading the raw **VR180** YouTube videos used by the
[Stereo4D: Learning How Things Move in 3D from Internet Stereo Videos] dataset.  
The script wraps **yt-dlp** with logging, resume support, exponential-back-off retries, and simple multi-threading so you can fetch thousands of clips.
It took like a week to download this dataset with multiple machines.

> **Status:** community tool – *not* an official Google DeepMind release.

---

## Installation

```bash
# 1. Create an isolated environment (optional)
conda create -n stereo4d_dl python=3.10
conda activate stereo4d_dl

# 2. Dependencies
pip install yt-dlp==2024.11.18 tqdm
````

**Why pin `yt-dlp` to `2024.11.18`?**
The Stereo4D authors found that later versions fail to fetch VR180 DASH streams;
issue #6 in the official repo recommends this specific build. ([GitHub][1])

You’ll also need **ffmpeg** in your `PATH` (yt-dlp uses it to mux audio/video).

---

## Quick start

```bash
python download_stereo4d.py \
  --url_file  urls/test_urls.txt \
  --output_dir ./stereo4d_raw \
  --batch_size 50 \
  --max_workers 8 \
  --verbose
```

* `--url_file` — plain-text file with one YouTube link per line (e.g. the lists
  released by Stereo4D).
* `--output_dir` — where the videos (`<VIDEO_ID>.mp4`) are stored.
* `--batch_size` — how many URLs to process before pausing (avoids long, fragile
  runs).
* `--max_workers` — parallel threads (I/O bound; 8-12 is usually safe).

Two helper logs are created alongside your list:

* `downloaded_<listname>_urls.txt` — successful (or pre-existing) downloads.
* `failed_<listname>_urls.txt` — anything that exhausted all retries.

Rerun the same command at any time; completed IDs are skipped automatically.

---

## Working with the Stereo4D pipeline

After the raw VR180 `.mp4/.webm` files are in place, follow **Step 2/6** of the
\[official Stereo4D pipeline] (rectification & perspective projection).
This downloader only covers **Step 1**. ([GitHub][2])

---

## Troubleshooting

| Symptom                                  | Fix                                                                          |
| ---------------------------------------- | ---------------------------------------------------------------------------- |
| `Video unavailable (removed or private)` | Unfortunately the clip is gone – remove the URL or look for mirrors.         |
| `Sign in to confirm you’re not a bot`    | Pass `--cookies-from-browser <browser>` or `--cookies-file <path>`.          |
| Only 1080p files appear in `-F` list     | The video was uploaded below 1440 p; the Stereo4D annotations may not align. |

---

## License

Distributed under the MIT License (see `LICENSE`).
Stereo4D assets are governed by their own terms; consult the original repo.

---

### Citation

If you use this tool or the dataset, please cite:

```
@inproceedings{jin2025stereo4d,
  title     = {Stereo4D: Learning How Things Move in 3D from Internet Stereo Videos},
  author    = {Linyi Jin and Richard Tucker and Zhengqi Li and David Fouhey and Noah Snavely and Aleksander Hołyński},
  booktitle = {CVPR},
  year      = {2025}
}
```

```

[official Stereo4D pipeline]: https://github.com/Stereo4d/stereo4d-code
[Stereo4D: Learning How Things Move in 3D from Internet Stereo Videos]: https://arxiv.org/abs/2412.09621
```

---

Happy downloading! 🚀

[1]: https://github.com/Stereo4d/stereo4d-code/issues/6 "How to download YouTube videos in VR180 format? · Issue #6 · Stereo4d/stereo4d-code · GitHub"
[2]: https://github.com/Stereo4d/stereo4d-code "GitHub - Stereo4d/stereo4d-code: Stereo4D dataset and processing code"
