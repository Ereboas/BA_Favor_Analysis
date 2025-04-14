import os
from pathlib import Path
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas

DATA_PATH = "students.csv"
df = pandas.read_csv(DATA_PATH)
student_ids = df["StudentID"].tolist()

AVATAR_DIR = Path("avatars")
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

def download_avatar(student_id):
    avatar_file = AVATAR_DIR / f"{student_id}.webp"
    if avatar_file.exists():
        return f"[SKIP] {student_id} 已存在"

    url = f"https://schaledb.com/images/student/collection/{student_id}.webp"
    try:
        response = requests.get(url, timeout=8)
        if response.status_code == 200:
            with open(avatar_file, "wb") as f:
                f.write(response.content)
            return f"[INFO] 成功下载 {student_id}"
        else:
            return f"[ERROR] 下载 {student_id} 失败，状态码: {response.status_code}"
    except Exception as e:
        return f"[ERROR] 下载 {student_id} 异常: {e}"

def download_avatars_concurrently(start_id=10000, end_id=30000, max_workers=32):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_avatar, student_id): student_id for student_id in student_ids}
        for future in as_completed(futures):
            print(future.result())

if __name__ == "__main__":
    download_avatars_concurrently()
