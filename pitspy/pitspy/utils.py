from typing import Any

def cls_python_path(cls: type[Any]) -> list[str]:
	# see: https://stackoverflow.com/questions/2020014/get-fully-qualified-class-name-of-an-object-in-python
	module = cls.__module__
	
	if module == 'builtins':
		return [cls.__qualname__]
	
	return [*module.split('.'), *cls.__qualname__.split('.')]
