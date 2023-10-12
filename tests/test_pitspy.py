from typing import Never, Any

from pitspy.core import PITSPY_TREE_ROOT, convert_tree, get_annotation_tree
from pitspy.types import PitspyNode

from tests.moda.a import ModAClass


def test_pitspy_tree() -> Never:
	assert PITSPY_TREE_ROOT.branches['tests'].branches['moda'].branches['a'].leafs['ModAClass']


def test_tree_convert() -> Never:
	new_tree = convert_tree(lambda v: v.__name__)
	
	assert new_tree.branches['tests'].branches['moda'].branches['a'].leafs['ModAClass'] == 'ModAClass'


def test_annotation_tree() -> Never:
	atree = get_annotation_tree()

	assert atree.branches['tests'].branches['moda'].branches['a'].leafs['ModAClass']
