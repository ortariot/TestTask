from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class AstroCore(ABC):
    @abstractmethod
    def compute_coordinate(
        self,
        *,
        calc_data: Any | None = None,
        tle: Any | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        step_seconds: int | None = None,
    ) -> list[dict[str, Any]]:
        pass
