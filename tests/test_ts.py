from typing import Never
import pathlib

from pitspy.converters.ts import (
	get_ts_annotation_tree, write_ts_annotation_tree_to_interfaces_ts
)


def test_ts_annotation_tree() -> Never:
	ts_tree = get_ts_annotation_tree()
	
	print(ts_tree)

	write_ts_annotation_tree_to_interfaces_ts(
		ts_tree,
		pathlib.Path('./testresult.ts')
	)
	
	assert False
