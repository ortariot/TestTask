from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient

from tests.conftest import build_payload, to_utc

pytestmark = pytest.mark.time_slicing


def parse_iso(ts: str) -> datetime:
    """Parse an ISO string, normalize to UTC for comparisons."""

    normalized = ts.replace("Z", "+00:00")
    return to_utc(datetime.fromisoformat(normalized))


def timestamps_from_response(body: dict[str, Any]) -> list[datetime]:
    return [parse_iso(p["timestamp"]) for p in body["points"]]


# ---------------------------------------------------------------------------
# 1. Number of points for different (start, end, step).
# ---------------------------------------------------------------------------

POINTS_COUNT_CASES = [
    pytest.param(
        "2026-07-28T04:00:00Z",
        "2026-07-28T05:00:00Z",
        10,
        361,
        id="1h-step10s-inclusive-end",
    ),
    pytest.param(
        "2026-07-28T04:00:00Z",
        "2026-07-28T04:01:00Z",
        10,
        7,
        id="1min-step10s-inclusive-end",
    ),
    pytest.param(
        "2026-07-28T04:00:00Z",
        "2026-07-28T04:00:10Z",
        10,
        2,
        id="10s-step10s-two-points",
    ),
    pytest.param(
        "2026-07-28T04:00:00Z",
        "2026-07-28T04:00:09Z",
        10,
        1,
        id="9s-step10s-single-point",
    ),
    pytest.param(
        "2026-07-28T04:00:00Z",
        "2026-07-28T04:00:01Z",
        1,
        2,
        id="1s-step1s-two-points",
    ),
    pytest.param(
        "2026-07-28T04:00:00Z",
        "2026-07-28T04:10:00Z",
        60,
        11,
        id="10min-step60s-inclusive-end",
    ),
    pytest.param(
        "2026-07-28T04:00:00Z",
        "2026-07-28T04:10:01Z",
        60,
        11,
        id="10min1s-step60s-floor-last",
    ),
    pytest.param(
        "2026-07-28T00:00:00Z",
        "2026-07-28T01:00:00Z",
        1,
        3601,
        id="1h-step1s-max-resolution",
    ),
]


@pytest.mark.parametrize("start, end, step, expected_count", POINTS_COUNT_CASES)
async def test_points_count_matches_expected(
    client: AsyncClient,
    start: str,
    end: str,
    step: int,
    expected_count: int,
) -> None:
    """Point count should match np.arange(start, end+1, step)."""

    payload = build_payload(start=start, end=end, step_seconds=step)

    response = await client.post("/coordinates_calculate", json=payload)

    assert response.status_code == status.HTTP_200_OK, response.text
    body = response.json()

    assert body["total"] == expected_count, (
        f"start={start}, end={end}, step={step}: "
        f"expected {expected_count}, got {body['total']}"
    )
    assert len(body["points"]) == expected_count


@pytest.mark.parametrize(
    "start, end, step",
    [
        pytest.param(
            "2026-07-28T04:00:00Z",
            "2026-07-28T05:00:00Z",
            10,
            id="1h-step10s",
        ),
        pytest.param(
            "2026-07-28T04:00:00Z",
            "2026-07-28T04:00:10Z",
            10,
            id="end-divisible-by-step",
        ),
        pytest.param(
            "2026-07-28T04:00:00Z",
            "2026-07-28T04:00:15Z",
            10,
            id="end-not-divisible-by-step",
        ),
    ],
)
async def test_first_and_last_timestamps(
    client: AsyncClient,
    start: str,
    end: str,
    step: int,
) -> None:
    """First point = start, last <= end, last > end - step."""

    payload = build_payload(start=start, end=end, step_seconds=step)

    response = await client.post("/coordinates_calculate", json=payload)

    assert response.status_code == status.HTTP_200_OK, response.text

    ts_list = timestamps_from_response(response.json())

    start_dt = parse_iso(start)
    end_dt = parse_iso(end)

    assert ts_list[0] == start_dt, f"First point {ts_list[0]} != start {start_dt}"

    assert ts_list[-1] <= end_dt, f"Last point {ts_list[-1]} > end {end_dt}"
    assert ts_list[-1] > end_dt - timedelta(seconds=step), (
        f"Last point {ts_list[-1]} too far from end {end_dt}"
    )


@pytest.mark.parametrize(
    "start, end, step",
    [
        pytest.param(
            "2026-07-28T04:00:00Z",
            "2026-07-28T04:05:00Z",
            10,
            id="5min-step10s",
        ),
        pytest.param(
            "2026-07-28T04:00:00Z",
            "2026-07-28T04:01:00Z",
            1,
            id="1min-step1s",
        ),
        pytest.param(
            "2026-07-28T04:00:00Z",
            "2026-07-28T04:10:00Z",
            60,
            id="10min-step60s",
        ),
    ],
)
async def test_step_between_consecutive_points_is_constant(
    client: AsyncClient,
    start: str,
    end: str,
    step: int,
) -> None:
    """Difference between adjacent timestamps should be exactly step."""

    payload = build_payload(start=start, end=end, step_seconds=step)

    response = await client.post("/coordinates_calculate", json=payload)

    assert response.status_code == status.HTTP_200_OK, response.text

    ts_list = timestamps_from_response(response.json())

    diffs = [
        (ts_list[i + 1] - ts_list[i]).total_seconds() for i in range(len(ts_list) - 1)
    ]

    unique_diffs = set(diffs)
    assert unique_diffs == {float(step)}, (
        f"Step is not constant: unique diffs = {unique_diffs}, "
        f"expected {{{float(step)}}}"
    )


@pytest.mark.parametrize(
    "start, end, step",
    [
        pytest.param(
            "2026-07-28T04:00:00Z",
            "2026-07-28T04:00:10Z",
            10,
            id="end-exact-multiple-step10s",
        ),
        pytest.param(
            "2026-07-28T04:00:00Z",
            "2026-07-28T04:01:00Z",
            60,
            id="end-exact-multiple-step60s",
        ),
        pytest.param(
            "2026-07-28T04:00:00Z",
            "2026-07-28T04:00:01Z",
            1,
            id="end-exact-multiple-step1s",
        ),
    ],
)
async def test_end_included_when_divisible_by_step(
    client: AsyncClient,
    start: str,
    end: str,
    step: int,
) -> None:
    """If end is a multiple of step, the last point should equal end."""

    payload = build_payload(start=start, end=end, step_seconds=step)

    response = await client.post("/coordinates_calculate", json=payload)

    assert response.status_code == status.HTTP_200_OK, response.text

    ts_list = timestamps_from_response(response.json())

    end_dt = parse_iso(end)
    assert ts_list[-1] == end_dt, (
        f"Last point {ts_list[-1]} != end {end_dt}, although end is a multiple of step={step}"
    )


@pytest.mark.parametrize(
    "start, end, step",
    [
        pytest.param(
            "2026-07-28T04:00:00Z",
            "2026-07-28T05:00:00Z",
            10,
            id="default-1h-step10s",
        ),
        pytest.param(
            "2026-07-28T00:00:00Z",
            "2026-07-28T00:05:00Z",
            5,
            id="5min-step5s",
        ),
    ],
)
async def test_service_receives_exact_time_params(
    client: AsyncClient,
    fake_service,
    start: str,
    end: str,
    step: int,
) -> None:

    payload = build_payload(start=start, end=end, step_seconds=step)

    response = await client.post("/coordinates_calculate", json=payload)

    assert response.status_code == status.HTTP_200_OK, response.text
    assert len(fake_service.calls) == 1

    call = fake_service.calls[0]
    assert call.start == parse_iso(start)
    assert call.end == parse_iso(end)
    assert call.step_seconds == step


async def test_points_are_strictly_monotonic(
    client: AsyncClient,
) -> None:

    payload = build_payload(
        start="2026-07-28T04:00:00Z",
        end="2026-07-28T04:05:00Z",
        step_seconds=10,
    )

    response = await client.post("/coordinates_calculate", json=payload)

    assert response.status_code == status.HTTP_200_OK, response.text

    ts_list = timestamps_from_response(response.json())

    for i in range(len(ts_list) - 1):
        assert ts_list[i] < ts_list[i + 1], (
            f"Monotonicity violated at position {i}: {ts_list[i]} >= {ts_list[i + 1]}"
        )


async def test_task_example_range_is_sliced_correctly(
    client: AsyncClient,
) -> None:

    payload = build_payload(
        start="2026-07-28T04:00:00Z",
        end="2026-07-28T05:00:00Z",
        step_seconds=10,
    )

    response = await client.post("/coordinates_calculate", json=payload)

    assert response.status_code == status.HTTP_200_OK, response.text
    body = response.json()

    expected_total = 361
    assert body["total"] == expected_total
    assert len(body["points"]) == expected_total

    ts_list = timestamps_from_response(body)
    assert ts_list[0] == parse_iso("2026-07-28T04:00:00Z")
    assert ts_list[-1] == parse_iso("2026-07-28T05:00:00Z")

    diffs = {
        (ts_list[i + 1] - ts_list[i]).total_seconds() for i in range(len(ts_list) - 1)
    }
    assert diffs == {10.0}
