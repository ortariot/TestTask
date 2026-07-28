import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, ParamSpec, TypeVar

import clickhouse_connect
from clickhouse_connect.driver import httputil
from clickhouse_connect.driver.client import Client

from .settings import settings

_P = ParamSpec("_P")
_R = TypeVar("_R")


class ClickHouseContainer:
    def __init__(self) -> None:
        self.client: Client | None = None
        self._executor: ThreadPoolExecutor | None = None

    def init(
        self, host: str, port: int, database: str, user: str, password: str
    ) -> None:
        if self.client is not None:
            return

        big_pool_mgr = httputil.get_pool_manager(maxsize=50, num_pools=10)

        self.client = clickhouse_connect.get_client(
            host=host,
            port=port,
            database=database,
            username=user,
            password=password,
            compress="zstd",
            connect_timeout=10,
            send_receive_timeout=30,
            pool_mgr=big_pool_mgr,
            autogenerate_session_id=False,
        )

        self._executor = ThreadPoolExecutor(
            max_workers=20, thread_name_prefix="clickhouse_io"
        )

    def close(self) -> None:
        if self.client:
            self.client.close()
            self.client = None
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None

    async def run_in_pool(
        self,
        func: Callable[_P, _R],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _R:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor, func, *args, **kwargs
        )

    async def insert_bulk(self, data: Any) -> None:
        if self.client is None:
            raise RuntimeError("ClickHouse client is not initialized")

        client = self.client

        def _execute() -> None:
            client.insert(
                table="coordinates",
                data=data,
                column_names=[
                    "task_id",
                    "chunk_index",
                    "timestamp",
                    "latitude",
                    "longitude",
                    "altitude",
                ],
            )

        await self.run_in_pool(_execute)

    async def stream_query(self, task_id: int) -> Any:
        if self.client is None:
            raise RuntimeError("ClickHouse client is not initialized")

        stmt = """
            SELECT timestamp, chunk_index, latitude, longitude, altitude
            FROM coordinates
            WHERE task_id = %s
            ORDER BY chunk_index, timestamp
        """

        return self.client.query_column_block_stream(
            stmt, parameters=(task_id,)
        )


ch_container = ClickHouseContainer()


def setup_clickhouse() -> None:
    ch_container.init(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        database=settings.clickhouse_db,
        user=settings.clickhouse_user,
        password=settings.clickhouse_password,
    )
