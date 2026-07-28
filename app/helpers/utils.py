from enum import Enum

from sqlalchemy import CheckConstraint


def enum_check_constraint(
    enum_cls: type[Enum], column_name: str
) -> CheckConstraint:
    """CheckConstraint for Enum."""
    values = ", ".join(f"'{item.value}'" for item in enum_cls)
    return CheckConstraint(
        f"{column_name} IN ({values})", name=f"ck_{column_name}"
    )
