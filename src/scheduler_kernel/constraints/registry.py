from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ConstraintCategory(StrEnum):
    PHYSICAL_HARD = "physical_hard"
    EXPLICIT_INSTITUTIONAL_HARD = "explicit_institutional_hard"
    TACIT_DOMAIN_HARD = "tacit_domain_hard"
    NEGOTIABLE_POLICY = "negotiable_policy"
    SOFT_PREFERENCE = "soft_preference"


@dataclass(frozen=True)
class ConstraintDefinition:
    code: str
    name: str
    category: ConstraintCategory
    relaxable: bool
    implemented: bool
    description: str


class ConstraintRegistry:
    def __init__(self, definitions: tuple[ConstraintDefinition, ...]) -> None:
        self._definitions = {definition.code: definition for definition in definitions}

    def get(self, code: str) -> ConstraintDefinition:
        return self._definitions[code]

    def all(self) -> tuple[ConstraintDefinition, ...]:
        return tuple(self._definitions.values())

    def relaxable_codes(self) -> tuple[str, ...]:
        return tuple(d.code for d in self._definitions.values() if d.relaxable)


def default_registry() -> ConstraintRegistry:
    c = ConstraintCategory
    return ConstraintRegistry(
        (
            ConstraintDefinition("H1_CLASS", "班級不可撞堂", c.PHYSICAL_HARD, False, True, "同一班同一時段最多一堂課。"),
            ConstraintDefinition("H2_TEACHER", "教師不可撞堂", c.PHYSICAL_HARD, False, True, "同一教師不能同時出現在兩處。"),
            ConstraintDefinition("H3_ROOM", "場地不可超額", c.PHYSICAL_HARD, False, True, "同一場地同一時段最多容納一堂課。"),
            ConstraintDefinition("H4_COMPLETE", "每堂課皆須排入", c.EXPLICIT_INSTITUTIONAL_HARD, False, True, "每個 lesson 必須恰好有一個時段與場地。"),
            ConstraintDefinition("H5_AVAIL", "教師不可排時段", c.EXPLICIT_INSTITUTIONAL_HARD, True, True, "教師明示不可授課的時段不得排課；只能經人工授權放寬。"),
            ConstraintDefinition("H6_DAILY_SUBJECT", "同科每日上限", c.TACIT_DOMAIN_HARD, True, True, "同一班同一科每日不超過設定上限。"),
            ConstraintDefinition("P1_MAIN_SPREAD", "主科分散", c.NEGOTIABLE_POLICY, True, True, "主科盡量分散到不同日，違反時記入目標函數。"),
            ConstraintDefinition("S1_TEACHER_SLOT", "教師時段偏好", c.SOFT_PREFERENCE, True, True, "只套用明示 prefer/avoid；unknown 與 indifferent 不產生懲罰。"),
        )
    )

