from typing import TypeVar, Any, Never, Callable

import inspect

from .types import AnnotationDict, PitspyNode
from .utils import cls_python_path

T = TypeVar('T')

PITSPY_TREE_ROOT = PitspyNode[type[Any]](
    branches=dict(),
    leafs=dict()
)

def _pitspy_tree_add_class(cls: type[Any]) -> None:
    global PITSPY_TREE_ROOT

    python_path = cls_python_path(cls)
    
    module_path, tail = python_path[:-1], python_path[-1]

    pathed_node: PitspyNode = PITSPY_TREE_ROOT
    for module_step in module_path:
        if module_step not in pathed_node.branches:
            pathed_node.branches[module_step] = PitspyNode[type[Any]](
                branches=dict(),
                leafs=dict()
            )
        pathed_node = pathed_node.branches[module_step]
    
    pathed_node.leafs[tail] = cls


class PitspyTypeMeta(type):
    def __new__(cls: type[T], name: str, bases: tuple, classdict: dict) -> type[T]:
        obj = super().__new__(cls, name, bases, classdict)
        if obj.__name__ != "PitspyType":
            _pitspy_tree_add_class(obj)
        return obj


class PitspyType(metaclass=PitspyTypeMeta):
    pass


S = TypeVar('S')


def convert_tree(
    node_callback: Callable[[T], S],
    tree: PitspyNode[T] | None = None
) -> PitspyNode[S]:
    """
        Walk the tree and recursively apply `node_callback`
        at every leaf to create a new tree based on the 
        return value of `node_callback`
    """
    def _convert_tree(node: PitspyNode[T]) -> PitspyNode[S]:
        new_node = PitspyNode[S](
            branches=dict(),
            leafs=dict()
        )

        for branch_key, branch in node.branches.items():
            new_node.branches[branch_key] = _convert_tree(branch)
        for leaf_key, leaf in node.leafs.items():
            new_node.leafs[leaf_key] = node_callback(leaf)
        
        return new_node

    root = tree if tree is not None else PITSPY_TREE_ROOT
    return _convert_tree(root)


def get_annotation_tree(
    annotation_reducer: Callable[[AnnotationDict], T] | None = None
) -> PitspyNode[T]:
    def annotater(cls: type[Any]) -> T:
        annotation_dict = inspect.get_annotations(cls)
        if annotation_reducer is not None:
            return annotation_reducer(annotation_dict)
        return annotation_dict 

    return convert_tree(annotater)


def traverse_tree_orderly(
    tree: PitspyNode[T],
    node_callback: Callable[[PitspyNode[T]], Never]
) -> Never:
    in_order: list[PitspyNode[T]] = []
    for branch_key, branch in tree.branches.items():
        if branch.leafs:
            node_callback(branch_key, branch)
        else:
            in_order.append(branch)
    
    try:
        branch = in_order.pop(0)
    except IndexError:
        branch = None

    while branch:
        traverse_tree_orderly(branch, node_callback)

        try:
            branch = in_order.pop(0)
        except IndexError:
            branch = None
