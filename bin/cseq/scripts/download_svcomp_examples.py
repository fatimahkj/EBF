# /usr/env python3

import requests
import zipfile
import os

from os.path import join, basename, splitext, isdir
from os import makedirs, remove
from shutil import move, rmtree

REPO_BASE_URL = "https://gitlab.com/sosy-lab/benchmarking/sv-benchmarks/-/"
DEFAULT_DOWNLOAD_LOCATION = "benchmark"

CATEGORIES = ["ConcurrencySafety-Main", "NoDataRace-Main"]


def get_set_file_url_for_category(category_name: str):
    return f"{REPO_BASE_URL}raw/main/c/{category_name}.set?inline=false"


def get_download_zip_for_folder(
    folder_name: str, zip_folder: str = DEFAULT_DOWNLOAD_LOCATION
) -> str:
    download_zip_url = (
        f"{REPO_BASE_URL}archive/main/sv-benchmarks-main.zip?path=c/{folder_name}"
    )

    r = requests.get(download_zip_url, allow_redirects=True)
    makedirs(zip_folder, exist_ok=True)
    path = join(zip_folder, folder_name + ".zip")

    with open(path, "wb") as zipf:
        zipf.write(r.content)

    return zipf.name


def extract_zip(path_to_zip_file: str, extract_to: str = DEFAULT_DOWNLOAD_LOCATION):
    with zipfile.ZipFile(path_to_zip_file, "r") as zip_ref:
        zip_ref.extractall(
            join(extract_to, splitext(basename(path_to_zip_file))[0])
        )


def move_files_in_subfolders_to_parent_folder(target_folder: str):
    for root, _, files in os.walk(target_folder):
        for f in files:
            move(join(root, f), join(target_folder, f))

    subfolders = [
        f for f in os.listdir(target_folder) if isdir(join(target_folder, f))
    ]
    for subfolder in subfolders:
        rmtree(join(target_folder, subfolder))


def download_files_for_category(category: str):
    url = get_set_file_url_for_category(category)

    pattern_data = requests.get(url).text

    patterns = [p for p in pattern_data.splitlines() if not p.strip().startswith("#")]
    folder_names = list(map(lambda p: p.split("/")[0], patterns))

    for folder_name in folder_names:
        zip_name = get_download_zip_for_folder(folder_name)
        extract_zip(zip_name)

        target_folder = join(DEFAULT_DOWNLOAD_LOCATION, folder_name)
        move_files_in_subfolders_to_parent_folder(target_folder)
        remove(zip_name)


def main():
    for category in CATEGORIES:
        download_files_for_category(category)


if __name__ == "__main__":
    main()
