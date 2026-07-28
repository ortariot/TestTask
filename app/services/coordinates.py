import asyncio
from collections.abc import AsyncGenerator
from contextlib import AbstractContextManager
from typing import IO, Any, cast

import clickhouse_connect.driver.exceptions as ch_exceptions

from core.clickhouse import ch_container
from core.exceptions import InfrastructureeOperationalException


class CoordinateService:
    @staticmethod
    async def get_coordinates_paginated(
        task_id: int, page: int, size: int
    ) -> tuple[int, int]:

        offset = (page - 1) * size

        def _fetch_data() -> list[dict[str, Any]]:
            stmt = """
                SELECT timestamp, chunk_index, latitude, longitude, altitude
                FROM coordinates
                WHERE task_id = %s
                ORDER BY chunk_index, timestamp
                LIMIT %s OFFSET %s
            """
            result = ch_container.client.query(
                stmt, parameters=(task_id, size, offset)
            )

            return [
                dict(zip(result.column_names, row, strict=False))
                for row in result.result_rows
            ]

        def _fetch_count() -> int:
            stmt = "SELECT count() FROM coordinates WHERE task_id = %s"
            result = ch_container.client.query(stmt, parameters=(task_id,))
            return int(result.result_rows[0][0])

        try:
            points, total_count = await asyncio.gather(
                asyncio.to_thread(_fetch_data), asyncio.to_thread(_fetch_count)
            )
            return points, total_count
        except (
            ch_exceptions.OperationalError,
            ch_exceptions.DatabaseError,
        ) as err:
            raise InfrastructureeOperationalException(
                "Failed to fetch paginated coordinates"
            ) from err

    async def get_coordinates_file_stream(
        self, task_id: int, offset_row: int, limit_row: int
    ) -> AsyncGenerator[bytes, None]:

        def _execute() -> AbstractContextManager[IO[bytes]]:
            stmt = """
                SELECT timestamp, chunk_index, latitude, longitude, altitude
                FROM coordinates
                WHERE task_id = %s
                ORDER BY chunk_index, timestamp
                LIMIT %s OFFSET %s
            """
            return cast(
                "AbstractContextManager[IO[bytes]]",
                ch_container.client.raw_stream(
                    query=stmt,
                    parameters=(task_id, limit_row, offset_row),
                    fmt="CSVWithNames",
                ),
            )

        try:
            raw_stream_context = await asyncio.to_thread(_execute)

            async def _bytes_generator() -> AsyncGenerator[bytes, None]:
                with raw_stream_context as stream:
                    for chunk in stream:
                        yield chunk

            return _bytes_generator()

        except (
            ch_exceptions.OperationalError,
            ch_exceptions.DatabaseError,
        ) as err:
            raise InfrastructureeOperationalException(
                "Database storage is unavailable"
            ) from err
