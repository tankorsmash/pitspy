from typing import Any, Never, TypeVar
import types

import datetime

from dataclasses import dataclass
from enum import Enum

from pathlib import Path

import humps

from pitspy.types import AnnotationDict, PitspyCustomMatch, PitspyNode
from pitspy.core import get_annotation_tree, traverse_tree_orderly, PitspyTypeMeta


class TsBaseType(Enum):
	NOT_BASE = ''
	UNDEFINED = 'undefined'
	NULL = 'null'
	NUMBER = 'number'
	STRING = 'string'
	BOOLEAN = 'boolean'
	CUSTOM = 'custom'
	GENERIC = 'generic'
	ANY = 'any'


class TsMutableType(Enum):
	NOT_MUT = 0
	DICT = 1
	ARRAY = 2
	TUPLE = 3


class TsOpType(Enum):
	NOT_OP = 0
	UNION = 1
	INTERSECT = 2


class TsPitspyCustomMatch(PitspyCustomMatch['TsAnnotation']):
	def match(self, py_cls: type[Any]) -> bool:
		try:
			return issubclass(py_cls.__class__, PitspyTypeMeta)
		except TypeError:
			return False

	def export(self, annotation: "TsAnnotation") -> str:
		return get_export_name(annotation.obj_ref.__name__, is_class=True)


class TsEnumCustomMatch(PitspyCustomMatch):
	has_block_export = True
	caught_enums: set[type[Enum]]

	def __init__(self):
		self.caught_enums = set()

	def match(self, py_cls: type[Any]) -> bool:
		try:
			is_enum = issubclass(py_cls, Enum)
		except TypeError:
			return False

		if is_enum:
			self.caught_enums.add(py_cls)

		return is_enum

	def export(self, annotation: "TsAnnotation") -> str:
		return get_export_name(annotation.obj_ref.__name__, is_enum=True)

	def export_block(self) -> str:
		output: list[str] = []

		for py_enum in self.caught_enums:
			enum_output = ""
			enum_name = get_export_name(py_enum.__name__, is_enum=True)

			enum_output = f"export enum {enum_name} {{\n"

			last_num_val: int | None = None
			for i, enum_choice in enumerate(py_enum):
				suffix = "," if i < len(py_enum) - 1 else ''
				enum_choice_output = enum_choice.name.upper()
				if isinstance(enum_choice.value, str):
					enum_output += f"\t{enum_choice_output} = '{enum_choice.value}'{suffix}\n"
					last_num_val = None
				elif isinstance(enum_choice.value, int) or isinstance(enum_choice.value, float):
					if last_num_val is None or last_num_val + 1 != enum_choice.value:
						enum_output += f"\t{enum_choice_output} = {enum_choice.value}{suffix}\n"
					else:
						enum_output += f"\t{enum_choice_output}{suffix}\n"
					last_num_val = enum_choice.value

			enum_output += "}"
			output.append(enum_output)

		return '\n\n'.join(output)


CUSTOM_HANDLERS: tuple[PitspyCustomMatch, ...] = (
	TsPitspyCustomMatch(), TsEnumCustomMatch()
    )

@dataclass(frozen=True, kw_only=True)
class TsAnnotation:
	op: TsOpType = TsOpType.NOT_OP
	base: TsBaseType = TsBaseType.NOT_BASE
	mutable: TsMutableType = TsMutableType.NOT_MUT
	arguments: list['TsAnnotation'] | None = None
	custom_match: PitspyCustomMatch | None = None
	obj_ref: type[Any] = type(None)

	@property
	def is_custom(self) -> bool:
		return self.base == TsBaseType.CUSTOM

	@property
	def is_op(self) -> bool:
		return self.op != TsOpType.NOT_OP

	@property
	def is_base(self) -> bool:
		return self.base != TsBaseType.NOT_BASE

	@property
	def is_mutable(self) -> bool:
		return self.mutable != TsMutableType.NOT_MUT


def _py_to_ts_base(py_cls: type[Any]) -> TsBaseType:
	if py_cls.__class__ == Any.__class__:
		return TsBaseType.ANY

	if py_cls.__class__ == TypeVar:
		return TsBaseType.GENERIC

	return {
		types.NoneType: TsBaseType.NULL,
		int: TsBaseType.NUMBER,
		float: TsBaseType.NUMBER,
		str: TsBaseType.STRING,
		bool: TsBaseType.BOOLEAN
	}.get(py_cls, TsBaseType.NOT_BASE)


def _py_to_ts_op(py_cls: type[Any]) -> TsOpType:
	if isinstance(py_cls, types.UnionType):
		return TsOpType.UNION

	return TsOpType.NOT_OP


def _py_to_ts_mutable(py_cls: type[Any]) -> TsMutableType:
	if not isinstance(py_cls, types.GenericAlias):
		return TsMutableType.NOT_MUT

	if py_cls.__origin__ == dict:
		return TsMutableType.DICT
	elif py_cls.__origin__ == list:
		return TsMutableType.ARRAY
	elif py_cls.__origin__ == tuple:
		return TsMutableType.TUPLE
	elif py_cls.__origin__ == set:
		return TsMutableType.ARRAY

	return TsMutableType.NOT_MUT


def py_annotation_to_ts_annotation(pytation: type[Any]) -> TsAnnotation:
	op = _py_to_ts_op(pytation)
	base = _py_to_ts_base(pytation)
	mutable = _py_to_ts_mutable(pytation)
	args: list[TsAnnotation] | None = None
	custom_match: PitspyCustomMatch | None = None

	for handler in CUSTOM_HANDLERS:
		if handler.match(pytation):
			custom_match = handler
			base = TsBaseType.CUSTOM
			break

	if base == TsBaseType.NOT_BASE and (
		op != TsOpType.NOT_OP
		or mutable != TsMutableType.NOT_MUT
	):
		args = [
			py_annotation_to_ts_annotation(a)
            for a in pytation.__args__ #type: ignore
		]

	return TsAnnotation(
		op=op,
		base=base,
		mutable=mutable,
		arguments=args,
		obj_ref=pytation,
		custom_match=custom_match
	)


def ts_annotation_reducer(annot: AnnotationDict) -> dict[str, TsAnnotation]:
	result: dict[str, TsAnnotation] = {}

	for var_name, annotation in annot.items():
		result[var_name] = py_annotation_to_ts_annotation(annotation)

	return result


def get_ts_annotation_tree() -> PitspyNode[TsAnnotation]:
	return get_annotation_tree(
		annotation_reducer=ts_annotation_reducer
	)


TS_HEADER = """\
/* This file is auto-generated by pitspy, it was last generated: {now} */\n\n
"""
def get_export_name(identifier: str, is_class: bool = False, is_enum: bool = False) -> str:
	if is_class:
		return f'{identifier}'
	elif is_enum:
		return humps.pascalize(identifier)
	return humps.camelize(identifier)

def ts_annotation_to_str(annotation: TsAnnotation, nested: bool = False) -> str:
	result = ""

	if annotation.is_custom and annotation.custom_match:
		result = annotation.custom_match.export(annotation)
	elif annotation.is_base:
		if annotation.base == TsBaseType.GENERIC:
			result = annotation.obj_ref.__name__
		else:
			result = annotation.base.value
	elif annotation.is_mutable:
		if annotation.mutable == TsMutableType.DICT:
			vt = ts_annotation_to_str(annotation.arguments[1])

			if annotation.arguments[0].base == TsBaseType.STRING:
				result = f"{{[key: string]: {vt}}}"
			else:
				kt = ts_annotation_to_str(annotation.arguments[0])
				result = f"Record<{kt}, {vt}>"
		elif annotation.mutable == TsMutableType.ARRAY:
			vt = ts_annotation_to_str(annotation.arguments[0])
			result = f"Array<{vt}>"
		elif annotation.mutable == TsMutableType.TUPLE:
			vts = ', '.join([ts_annotation_to_str(a) for a in annotation.arguments])
			result = f"[{vts}]"
	elif annotation.is_op:
		if annotation.op == TsOpType.UNION:
			result = ' | '.join([ts_annotation_to_str(a, nested=True) for a in annotation.arguments])
	elif annotation.obj_ref:
		result = annotation.obj_ref

	if result and nested and annotation.is_op:
		return f'({result})'

	return result

def write_ts_annotation_tree_to_interfaces_ts(
	tree: PitspyNode[TsAnnotation],
	output_path: Path
) -> None:
	header = TS_HEADER.format(now=datetime.datetime.now().isoformat())

	with open(output_path, encoding='UTF-8', mode='w') as output:
		output.write(header)

		for handler in CUSTOM_HANDLERS:
			if handler.has_block_export:
				output.write(handler.export_block())
				output.write('\n\n')

		def write_node(node_key: str, node: PitspyNode[TsAnnotation]) -> None:
			for leaf_key, leaf in node.leafs.items():
				type_name = get_export_name(leaf_key, is_class=True)

				generics: list[str] = []
				for annot in leaf.values():
					if annot.base != TsBaseType.GENERIC:
						continue

					gen_name = annot.obj_ref.__name__

					if not annot.obj_ref.__constraints__:
						generics.append(gen_name)
						continue
					print("cons", annot.obj_ref.__constraints__)
					constraints = ' | '.join([
						ts_annotation_to_str(
							py_annotation_to_ts_annotation(c),
							nested=True
						)
						for c in annot.obj_ref.__constraints__
					])

					generics.append(f'{gen_name} extends {constraints}')

				if generics:
					joined_generics = ', '.join(generics)
					output.write(f'export declare type {type_name}<{joined_generics}> = {{\n')
				else:
					output.write(f'export declare type {type_name} = {{\n')
				for member_key, member in leaf.items():
					converted_annotation = ts_annotation_to_str(member)
					camelized = get_export_name(member_key)
					output.write(f'\t{camelized}: {converted_annotation};\n')

				output.write(f'}};\n\n')

		traverse_tree_orderly(
			tree,
			write_node
		)
