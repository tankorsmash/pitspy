from typing import TypeVar, Generic, Self, Any, Never
from dataclasses import dataclass

T = TypeVar('T')


@dataclass
class PitspyNode(Generic[T]):
	branches: dict[str, Self]
	leafs: dict[str, T]


AnnotationDict = dict[str, Any]


class PitspyCustomMatch(Generic[T]):
	has_block_export: bool = False

	def match(self, py_cls: type[Any]) -> bool:
		raise NotImplementedError

	def export(self, annotation: T) -> str:
		raise NotImplementedError

	def export_block(self) -> str:
		raise NotImplementedError
