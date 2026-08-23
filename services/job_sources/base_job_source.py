from abc import ABC, abstractmethod

from models.job import Job


class JobSource(ABC):

    @abstractmethod
    def search(
        self,
        keywords: str,
        location: str,
        page: int = 1,
        results_per_page: int = 20,
    ) -> list[Job]:
        pass
