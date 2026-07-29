from __future__ import annotations

from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient

from tests.conftest import build_payload

pytestmark = pytest.mark.validation


def _tamper(payload: dict[str, Any], **overrides: Any) -> dict[str, Any]:

    import copy

    result = copy.deepcopy(payload)

    content_keys = {"content_type", "line1", "line2", "name"}

    for key, value in overrides.items():
        if key in content_keys:
            field = "content" if key == "content_type" else key
            result["content"][field] = value
        else:
            result[key] = value

    return result


VALID_CASES = [
    pytest.param(
        "Perfectly valid TLE request",
        build_payload(),
        id="happy-path-iss-tle",
    ),
    pytest.param(
        "Valid request with name=None",
        build_payload(name=None),
        id="happy-path-without-name",
    ),
    pytest.param(
        "Minimum allowed step_seconds=1",
        build_payload(step_seconds=1),
        id="happy-path-min-step",
    ),
    pytest.param(
        "Maximum allowed step_seconds=60",
        build_payload(step_seconds=60),
        id="happy-path-max-step",
    ),
    pytest.param(
        "Time difference exactly 1 second with step=1",
        build_payload(
            start="2026-07-28T04:00:00Z",
            end="2026-07-28T04:00:01Z",
            step_seconds=1,
        ),
        id="happy-path-tiny-range",
    ),
]


@pytest.mark.parametrize("description, payload", VALID_CASES)
async def test_valid_request_is_accepted(
    client: AsyncClient,
    fake_service,
    description: str,
    payload: dict[str, Any],
) -> None:

    response = await client.post("/coordinates_calculate", json=payload)

    assert response.status_code == status.HTTP_200_OK, (
        f"[{description}] expected 200, got {response.status_code}: {response.text}"
    )

    body = response.json()
    assert "total" in body, f"[{description}] no total in response"
    assert body["total"] >= 1

    assert len(fake_service.calls) == 1, f"[{description}] service was not called"
    assert fake_service.calls[0].step_seconds == payload["step_seconds"]


INVALID_TLE_CASES = [
    pytest.param(
        "Line1 shorter than 69 characters",
        {
            "line1": "1 05398U 71067E   26209.18109351  .00000744  00000+0  23505-3 0  999"
        },
        id="line1-too-short",
    ),
    pytest.param(
        "Line1 longer than 69 characters",
        {
            "line1": (
                "1 05398U 71067E   26209.18109351  .00000744  "
                " 00000+0  23505-3 0  99955"
            )
        },
        id="line1-too-long",
    ),
    pytest.param(
        "Line1 does not start with '1 '",
        {
            "line1": "2 05398U 71067E   26209.18109351  .00000744  00000+0  23505-3 0  9995"
        },
        id="line1-wrong-prefix",
    ),
    pytest.param(
        "Line2 does not start with '2 '",
        {
            "line2": "1 05398  87.6249 327.4279 0062195  96.8316 263.9965 14.37917437879777"
        },
        id="line2-wrong-prefix",
    ),
    pytest.param(
        "Mismatched satellite number in lines",
        {
            "line1": (
                "1 99999U 71067E   26209.18109351  .00000744   00000+0  23505-3 0  9999"
            ),
            "line2": (
                "2 99999  87.6249 327.4279 0062195  96.8316 263.9965 14.37917437879777"
            ),
        },
        id="sat-num-mismatch",
    ),
    pytest.param(
        "Empty TLE strings",
        {"line1": "", "line2": ""},
        id="empty-tle",
    ),
    pytest.param(
        "Invalid line1 checksum (last char)",
        {
            "line1": (
                "1 05398U 71067E   26209.18109351  .00000744   00000+0  23505-3 0  9990"
            )
        },
        id="line1-bad-checksum",
    ),
    pytest.param(
        "Invalid line2 checksum (last char)",
        {
            "line2": (
                "2 05398  87.6249 327.4279 0062195  96.8316 263.9965 14.37917437879770"
            )
        },
        id="line2-bad-checksum",
    ),
    pytest.param(
        "name longer than 24 characters",
        {"name": "A" * 25},
        id="name-too-long",
    ),
]


@pytest.mark.parametrize("description, overrides", INVALID_TLE_CASES)
async def test_invalid_tle_is_rejected(
    client: AsyncClient,
    fake_service,
    description: str,
    overrides: dict[str, Any],
) -> None:

    payload = _tamper(build_payload(), **overrides)

    response = await client.post("/coordinates_calculate", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
        f"[{description}] expected 422, got {response.status_code}: {response.text}"
    )

    assert not fake_service.calls, (
        f"[{description}] service should not have been called"
    )


STEP_CASES = [
    pytest.param("step=0 (below minimum)", 0, id="step-zero"),
    pytest.param("step=-5 (negative)", -5, id="step-negative"),
    pytest.param("step=61 (above maximum)", 61, id="step-too-large"),
    pytest.param("step=100 (clearly above maximum)", 100, id="step-huge"),
]


@pytest.mark.parametrize("description, step", STEP_CASES)
async def test_invalid_step_seconds(
    client: AsyncClient,
    fake_service,
    description: str,
    step: int,
) -> None:
    payload = build_payload(step_seconds=step)

    response = await client.post("/coordinates_calculate", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
        f"[{description}] expected 422, got {response.status_code}"
    )
    assert not fake_service.calls


DATE_CASES = [
    pytest.param(
        "end equals start",
        {"start": "2026-07-28T04:00:00Z", "end": "2026-07-28T04:00:00Z"},
        id="end-equal-start",
    ),
    pytest.param(
        "end before start",
        {"start": "2026-07-28T05:00:00Z", "end": "2026-07-28T04:00:00Z"},
        id="end-before-start",
    ),
    pytest.param(
        "Invalid start format (gibberish)",
        {"start": "not-a-valid-timestamp", "end": "2026-07-28T05:00:00Z"},
        id="bad-start-format",
    ),
    pytest.param(
        "Invalid end format",
        {"start": "2026-07-28T04:00:00Z", "end": "not-a-date"},
        id="bad-end-format",
    ),
    pytest.param(
        "Missing start field",
        {"start": None},
        id="missing-start",
    ),
    pytest.param(
        "Missing end field",
        {"end": None},
        id="missing-end",
    ),
    pytest.param(
        "Range completely missing",
        {"start": None, "end": None},
        id="missing-range",
    ),
]


@pytest.mark.xfail(
    reason=(
        "BUG: validator _end_after_start in calcreq.py compares "
        "naive and aware datetime → TypeError → HTTP 500 instead of 422. "
    ),
    strict=True,
)
async def test_mixed_tz_awareness_is_handled_gracefully(
    client: AsyncClient,
    fake_service,
) -> None:

    payload = build_payload(
        start="2026-07-28 04:00:00",
        end="2026-07-28T05:00:00Z",
    )

    response = await client.post("/coordinates_calculate", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
        f"Expected 422, got {response.status_code}: {response.text}"
    )
    assert not fake_service.calls


@pytest.mark.parametrize("description, overrides", DATE_CASES)
async def test_invalid_date_range(
    client: AsyncClient,
    fake_service,
    description: str,
    overrides: dict[str, Any],
) -> None:
    base = build_payload()

    for key, value in overrides.items():
        if value is None:
            base.pop(key, None)
        else:
            base[key] = value

    response = await client.post("/coordinates_calculate", json=base)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
        f"[{description}] expected 422, got {response.status_code}: {response.text}"
    )
    assert not fake_service.calls


@pytest.mark.parametrize(
    "description, mutator",
    [
        pytest.param(
            "Missing entire content block",
            lambda p: {k: v for k, v in p.items() if k != "content"},
            id="missing-content-block",
        ),
        pytest.param(
            "Invalid content.content (discriminator)",
            lambda p: {**p, "content": {**p["content"], "content": "orb"}},
            id="bad-discriminator",
        ),
        pytest.param(
            "Missing step_seconds entirely",
            lambda p: {k: v for k, v in p.items() if k != "step_seconds"},
            id="missing-step-field",
        ),
    ],
)
async def test_structural_payload_errors(
    client: AsyncClient,
    fake_service,
    description: str,
    mutator,
) -> None:
    payload = mutator(build_payload())

    response = await client.post("/coordinates_calculate", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
        f"[{description}] expected 422, got {response.status_code}: {response.text}"
    )
