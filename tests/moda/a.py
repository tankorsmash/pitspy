from typing import Any, TypeVar, Generic
from enum import Enum
from pitspy.core import PitspyType

X = TypeVar('X', str, dict[str, list[int]])
Y = TypeVar('Y')


class ReffedEnum(Enum):
	ENUM_ONE = 0
	ENUM_TWO = 1
	ENUM_FIVE = 5
	ENUM_WORD = 'word'


class ModAClass(PitspyType):
	x: int
	y: list[str | None] | None
	z: (str | bool) | (int | dict[str, Any])
	choice: ReffedEnum


class ModABClass(PitspyType):
	camel_case: str
	a_ref: list[ModAClass]
	choice: list[ReffedEnum]


class ModACGenClass(Generic[X,Y], PitspyType):
	gen_var: X
	gen_autre: Y
	gen_list: list[X] | str
	gen_dict: dict[X, tuple[X, int, ReffedEnum]]

