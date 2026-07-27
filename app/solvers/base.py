from abc import ABC, abstractmethod


class AstroCore(ABC):
    @abstractmethod
    def compute_coordinate(self, *args, **kwargd):
        pass
