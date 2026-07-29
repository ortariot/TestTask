class BaseDomainException(Exception):
    """App logic exception base."""

    pass


class InfrastructureOperationalException(BaseDomainException):
    """Infrastructure exception."""

    pass


class TaskNotFinishedException(BaseDomainException):
    def __init__(self, task_id: int, current_status: str):
        self.task_id = task_id
        self.current_status = current_status
        super().__init__(
            f"Task {task_id} is not finished yet. Status: {current_status}"
        )
