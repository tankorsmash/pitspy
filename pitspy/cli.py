from typing import Never

import argparse

def main() -> Never:
	parser = argparse.ArgumentParser(
		prog="Pitspy",
		description="",
		epilog=""
	)
	
	parser.add_argument('-v', '--verbose', action='store_true', help='How noisy do you want it?')

	args = parser.parse_args()

