#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
# Uses multiprocessing pool to generate and test lots of puzzles. Puzzles
# which take too long to solve are discarded.

DISCARD_TIMEOUT = 15
POOL_SIZE = 4
PUZZLE_COUNT = 100
BOARD_SIZE = 11
VERBOSE=True

from pykakuro import kakuro
from multiprocessing import Pool, TimeoutError
import traceback
from pathlib import Path

set_cache_path = Path('.set_cache')

if not set_cache_path.exists():
  kakuro._generate_set_cache()

def f(i):
  k = kakuro.gen_random(BOARD_SIZE, BOARD_SIZE, seed=i, is_solved=False)
  success = k.solve(timeout=DISCARD_TIMEOUT, timeout_exception=False)
  if success:
    try:
      k.check_solution(k.solutions[0].data)
      return i, k
    except Exception as e:
      print(f"Got exception {type(e).__name__}, {str(e)} for puzzle w/ seed {i}: \n{k.get_lol()} \nsolution : \n{k.solutions[0].get_lol()}")
      
      if VERBOSE:
        print("="*50)
        print("Traceback: ")
        print(traceback.format_exc())
        print("="*50)
      return i, e
  else:
    return i, None

pool = Pool(POOL_SIZE)
num_failures = 0

for seed, puzzle in pool.imap_unordered(f, list(range(PUZZLE_COUNT)), 10):
  if isinstance(puzzle, Exception):
    num_failures +=1
  elif puzzle:
    print("{0}: {1} {2}".format(seed, repr(puzzle), puzzle.difficulty))
  else:
    print("{0}: Too complex".format(seed))

print(f"Failure perc = {num_failures/PUZZLE_COUNT} %")
