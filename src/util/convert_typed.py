#!/usr/bin/env python
# Converts a more easily typed format like so:
#   0 0.2 0.3
#   5.0 1 1
# into valid puzzles.

import sys
import re

with open(sys.argv[1]) as f:
  d = f.read()

  d = d.replace("\n", ",\n")
  d = d.replace(" ", ", ")

  d = re.sub(r'([0-9]+)[.]([0-9]+)', r'(\1,\2)', d)

with open(sys.argv[2], 'w') as f:
  f.write(d)
