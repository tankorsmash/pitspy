from typing import Any, Never, TypeVar, Self
import types

from operator import attrgetter

import datetime

from dataclasses import dataclass
from enum import Enum

from pathlib import Path

# import humps

from pitspy.types import AnnotationDict, PitspyCustomMatch, PitspyNode
from pitspy.core import get_annotation_tree, traverse_tree_orderly, PitspyTypeMeta

""" elm

module MyModule exposing (Foo, GenericFoo)


type Colors = Red | Green | Blue

type alias Foo = {
    name: String;
    name2: String;
    age: Int;
	color: Colors;
}
type alias GenericFoo t = {
    name: String;
    generic: t;
    age: Int;
}
"""


ELM_HEADER = """\

import Json.Decode exposing (Decoder, field, map, string, int, float, bool, list, dict, at, andThen, oneOf, fail, succeed)
import Json.Encode exposing (Value, object, string, int, float, bool, list, dict, null, encode, decodeValue, decodeString, decodeInt, decodeFloat, decodeBool, decodeList, decodeDict, decodeNull, decodeValue, decodeObject, decodeField, decodeAt, decodeAndThen, decodeOneOf, decodeFail, decodeSucceed)
"""

class TsBaseType(Enum):
	NOT_BASE = ''
	UNDEFINED = 'undefined'
	NULL = 'null'
	INT = 'Int'
	FLOAT = 'Float'
	STRING = 'String'
	BOOLEAN = 'boolean'
	CUSTOM = 'custom'
	GENERIC = 'generic'
	ANY = 'Json.Decode.Value'


class TsMutableType(Enum):
	NOT_MUT = 0
	DICT = 1
	ARRAY = 2
	TUPLE = 3


class TsOpType(Enum):
	NOT_OP = 0
	UNION = 1
	INTERSECT = 2

class ElmPitspyCustomMatch(PitspyCustomMatch['ElmAnnotation']):
	def match(self, py_cls: type[Any]) -> bool:
		try:
			return issubclass(py_cls.__class__, PitspyTypeMeta)
		except TypeError:
			return False

	def export(self, annotation: "ElmAnnotation") -> str:
		return annotation.obj_ref.__name__

class ElmEnumCustomMatch(PitspyCustomMatch):
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
			e_types : list[type] = list(set(map(lambda e: type(e.value), py_cls)))
			if len(e_types) > 1 or len(e_types) == 0:
				return False

			if e_types[0] not in [int, float, str]:
				return False

			self.caught_enums.add(py_cls)

		return is_enum

	def export(self, annotation: "ElmAnnotation") -> str:
		return annotation.obj_ref.__name__

	def export_block(self) -> str:
		output: list[str] = []

		for py_enum in self.caught_enums:
			enum_output = ""
			enum_name = py_enum.__name__

			#type definition
			enum_output  = f"type {enum_name} =\n  "
			enum_output += "\n  | ".join(map(lambda e: e.name.title(), py_enum))


			enum_output += "\n\n\n"

			if type(list(py_enum)[0].value) != str:
				raise Exception("Only string enums are supported")

			#convert enum to target_type
			target_type = "String"
			#TODO: support other types
			convert_from_enum_name = f"convert{enum_name}To{target_type}"
			enum_output += f"{convert_from_enum_name} : {enum_name} -> {target_type}\n"
			enum_output += f"{convert_from_enum_name} e =\n  case e of\n"
			for e in py_enum:
				enum_output += f"    {e.name.title()} -> \"{e.value}\"\n"

			#convert target_type to enum
			convert_to_enum_name = f"convert{target_type}To{enum_name}"
			enum_output += f"\n\n{convert_to_enum_name} : {target_type} -> Maybe {enum_name}\n"
			enum_output += f"{convert_to_enum_name} e =\n  case e of\n"
			for e in py_enum:
				enum_output += f"    \"{e.value}\" -> Just {e.name.title()}\n"
			enum_output += f"    _ -> Nothing\n"

			#json encoder
			enum_output += f"\n\nencode{enum_name} : {enum_name} -> Value\n"
			enum_output += f"encode{enum_name} =\n  {convert_from_enum_name} >> Encode.string\n"

			#json decoder
			decoder_name = "Decode.string"
			#TODO: support other types
			enum_output += f"\n\ndecode{enum_name} : Decoder {enum_name}\n"
			enum_output += f"decode{enum_name} =\n  {decoder_name} >> Decode.andThen {convert_to_enum_name}\n"

			output.append(enum_output)

		return '\n\n'.join(output)


CUSTOM_HANDLERS : tuple[PitspyCustomMatch, ...] = (
	ElmEnumCustomMatch(),
	ElmPitspyCustomMatch()
)


@dataclass(frozen=True, kw_only=True)
class ElmAnnotation:
	op: TsOpType = TsOpType.NOT_OP
	base: TsBaseType = TsBaseType.NOT_BASE
	mutable: TsMutableType = TsMutableType.NOT_MUT
	arguments: list[Self] | None = None
	custom_match: PitspyCustomMatch | None = None
	obj_ref: type[Any] | None = None

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
		int: TsBaseType.INT,
		float: TsBaseType.FLOAT,
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

def py_annotation_to_elm_annotation(pytation: type[Any]) -> 'ElmAnnotation':
	op = _py_to_ts_op(pytation)
	base = _py_to_ts_base(pytation)
	mutable = _py_to_ts_mutable(pytation)
	args: list['ElmAnnotation'] | None = None
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
			py_annotation_to_elm_annotation(a)
			for a in pytation.__args__ #type: ignore
		]

		return ElmAnnotation(
			op=op,
			base=base,
			mutable=mutable,
			arguments=args,
			obj_ref=pytation,
			custom_match=custom_match
		)

	return ElmAnnotation(
		op=op,
		base=base,
		mutable=mutable,
		arguments=args,
		obj_ref=pytation,
		custom_match=custom_match
	)


def elm_annotation_reducer(annot: AnnotationDict) -> AnnotationDict:
# def elm_annotation_reducer(annot: AnnotationDict) -> 'ElmAnnotation':
	result: dict[str, 'ElmAnnotation'] = {}

	for var_name, annotation in annot.items():
		result[var_name] = py_annotation_to_elm_annotation(annotation)

	return result

def ts_annotation_to_str(annotation: ElmAnnotation, nested: bool = False) -> str:
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



def get_elm_annotation_tree() -> PitspyNode[AnnotationDict]:
	return get_annotation_tree(
		annotation_reducer=elm_annotation_reducer
	)

def write_elm_annotation_tree_to_interfaces_elm(
	tree: PitspyNode[ElmAnnotation],
	output_path: Path
	) -> None:
	header = ELM_HEADER.format(now=datetime.datetime.now().isoformat())

	with output_path.open(encoding='UTF-8', mode='w') as output:
		output.write(header)

		for handler in CUSTOM_HANDLERS:
			if handler.has_block_export:
				output.write(handler.export_block())
				output.write('\n\n')

		def write_node(_: str, node: PitspyNode['ElmAnnotation']) -> None:
			for type_name, leaf in node.leafs.items():

				generics: list[str] = []
				for annot in leaf.values():
					if annot.base != TsBaseType.GENERIC:
						continue

					gen_name = annot.obj_ref.__name__
					generics.append(gen_name)

					# if not annot.obj_ref.__constraints__:
					# 	generics.append(gen_name)
					# 	continue
					# print("cons", annot.obj_ref.__constraints__)
					# constraints = ' | '.join([
					# 	ts_annotation_to_str(
					# 		py_annotation_to_elm_annotation(c),
					# 		nested=True
					# 	)
					# 	for c in annot.obj_ref.__constraints__
					# ])

					# generics.append(f'{gen_name} extends {constraints}')

				joined_generics = ', '.join(generics)
				output.write(f'type alias {type_name} {joined_generics} = {{\n')

				my_list = []
				for member_key, member in leaf.items():
					converted_annotation = ts_annotation_to_str(member)
					my_list.append(f' {member_key}: {converted_annotation}')

				output.write('\n,'.join(my_list))

				output.write(f'}}\n\n')

		traverse_tree_orderly(
				tree,
				write_node
			)




