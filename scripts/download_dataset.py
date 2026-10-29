"""Download the clothing-dataset (CC0-1.0) and extract only its data files.

Only `images.csv` and `images/*.jpg` are extracted; nothing from the archive is executed.
Usage: python scripts/download_dataset.py [--data-dir data]
"""

import argparse
import shutil
import sys
import tarfile
import time
import urllib.request
from pathlib import Path, PurePosixPath

URL = "https://codeload.github.com/alexeygrigorev/clothing-dataset/tar.gz/refs/heads/master"
ATTEMPTS = 5
STALL_TIMEOUT_S = 60


def download(url: str, dest: Path) -> None:
    """Stream the archive to disk, retrying from scratch if the connection stalls."""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(url, timeout=STALL_TIMEOUT_S) as response, dest.open("wb") as out:
                received = 0
                while chunk := response.read(1 << 20):
                    out.write(chunk)
                    received += len(chunk)
                    print(f"\r  {received / 1e6:6.1f} MB", end="", flush=True)
            print()
            return
        except (TimeoutError, OSError) as exc:
            print(f"\n  attempt {attempt}/{ATTEMPTS} failed: {exc}")
            time.sleep(2 * attempt)
    sys.exit("Download failed. Check your connection and re-run.")


def extract_data_files(archive: Path, target: Path) -> int:
    """Extract images.csv and images/*.jpg into `target`, rejecting unsafe paths."""
    target.mkdir(parents=True, exist_ok=True)
    (target / "images").mkdir(exist_ok=True)
    count = 0
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            if not member.isfile():
                continue
            parts = PurePosixPath(member.name).parts[1:]  # drop the "clothing-dataset-master/" prefix
            if ".." in parts or not parts:
                continue
            is_csv = parts == ("images.csv",)
            is_image = len(parts) == 2 and parts[0] == "images" and parts[1].endswith(".jpg")
            if not (is_csv or is_image):
                continue
            source = tar.extractfile(member)
            if source is None:
                continue
            with source, (target.joinpath(*parts)).open("wb") as out:
                shutil.copyfileobj(source, out)
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    args = parser.parse_args()

    target = args.data_dir / "raw" / "clothing-dataset"
    if (target / "images.csv").exists():
        print(f"Dataset already present at {target}")
        return

    archive = args.data_dir / "raw" / "clothing-dataset.tar.gz"
    archive.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading clothing-dataset (CC0-1.0) to {archive}")
    download(URL, archive)
    n = extract_data_files(archive, target)
    archive.unlink()
    print(f"Extracted {n} files to {target}")


if __name__ == "__main__":
    main()
