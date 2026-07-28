from fastapi import Depends, HTTPException, Path, status

from core.exceptions import TaskNotFinishedException
from models import TaskStatus
from repositories import CalculationTaskRepository, get_calc_task_repo


async def validate_task_finished(
    task_id: int = Path(..., description="task id"),
    task_repo: CalculationTaskRepository = Depends(get_calc_task_repo),
) -> int:

    task = await task_repo.get_by_id(task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    if task.status != TaskStatus.SUCCESS:
        raise TaskNotFinishedException(
            task_id=task_id, current_status=task.status
        )

    return task_id
