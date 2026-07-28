from abc import ABC, abstractmethod
from typing import Any

from schemas.calcreq import CalculationRequest


class AstroCore(ABC):
    @abstractmethod
    def compute_coordinate(
        self,
        calc_data: CalculationRequest,
    ) -> list[dict[str, Any]]:
        pass
