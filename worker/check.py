import math
from datetime import datetime, timedelta

start = datetime.fromisoformat("2026-07-22T21:22:40.541Z")
stop = datetime.fromisoformat("2026-07-27T21:22:40.541Z")


total_seconds = (stop - start).total_seconds()
total_points = math.ceil(total_seconds / 30)
chunks_count = math.ceil(total_points / 5000)

res = []

for idx in range(chunks_count):
    chunk_start_sec = idx * 5000 * 30
    chunk_end_sec = min((idx + 1) * 5000 * 30, total_seconds)
    chunk_start = start + timedelta(seconds=chunk_start_sec)
    chunk_end = start + timedelta(seconds=chunk_end_sec)

    res.append((chunk_start, chunk_end))


print(len(res))
print(res)
