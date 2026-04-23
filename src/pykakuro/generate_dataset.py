#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
# Uses multiprocessing pool to generate and test lots of puzzles. Puzzles
# which take too long to solve are discarded.

DISCARD_TIMEOUT = 5
POOL_SIZE = 8
START_ID = 0
PUZZLE_COUNT = 100000
BOARD_SIZE = 11
VERBOSE=False

from pykakuro import kakuro
from multiprocessing import Pool, TimeoutError
import traceback
import pandas as pd
from pathlib import Path

SAVE_PATH = Path("/hpc/group/tdunn/asabath/ece790_diffusion/Project/ar-diffusion-2d/data/kakuro") / "kakuro_100k.parquet"
set_cache_path = Path('.set_cache')

if not set_cache_path.exists():
  kakuro._generate_set_cache()

def f(i):
  k = kakuro.gen_random(BOARD_SIZE, BOARD_SIZE, seed=i, is_solved=False)
  success = k.solve(timeout=DISCARD_TIMEOUT, timeout_exception=False)
  if success:
    try:
      k.check_solution(k.solutions[0].data)
      return i, k, None
    except Exception as e:
      print(f"Got exception {type(e).__name__}, {str(e)} for puzzle w/ seed {i}: \n{k.get_lol()} \nsolution : \n{k.solutions[0].get_lol()}")
      
      if VERBOSE:
        print("="*50)
        print("Traceback: ")
        print(traceback.format_exc())
        print("="*50)
      return i, k, e
  else:
    return i, k, kakuro.SolutionUnsolvedException

pool = Pool(POOL_SIZE)
num_failures = 0
puzzles = {
  'seed':                   [],
  'puzzle':                 [],
  'solution':               [],
  'difficulty':             [],
  'min_value':              [],
  'max_value':              [],
  'num_entry_squares':      [],
  'search_space_size':      [],
  'brute_force_size':       [],
  'is_exclusive':           [],
}

batch = []
batch_size = 10000
# batch_size = 5
batch_id = START_ID // batch_size


for seed, puzzle, err in pool.imap_unordered(f, list(range(START_ID, START_ID + PUZZLE_COUNT)), 10):
  row = {
        "seed": seed,
        "puzzle": kakuro.print_lol(puzzle.data, puzzle.x_size, center_cells=False),
        "solution": kakuro.print_lol(puzzle.master_solution, puzzle.x_size, center_cells=False),
        "difficulty": puzzle.difficulty,
        "min_value": puzzle.min_val,
        "max_value": puzzle.max_val,
        "num_entry_squares": puzzle.num_entry_squares,
        "search_space_size": str(puzzle.search_space_size),
        "brute_force_size": puzzle.brute_force_size ,
        "is_exclusive": puzzle.is_exclusive and len(puzzle.solutions) <= 1,
    }

  batch.append(row)

  if len(batch) >= batch_size:
    df = pd.DataFrame(batch)
    df.to_parquet(str(SAVE_PATH.parent / f"part_{batch_id:05}.parquet"), engine="pyarrow")
    batch.clear()
    batch_id+=1


  if isinstance(err, Exception):
    num_failures +=1
  elif puzzle:
    print("{0}: {1} {2}".format(seed, repr(puzzle), puzzle.difficulty))
  else:
    print("{0}: Too complex".format(seed))

print(f"Failure perc = {num_failures/PUZZLE_COUNT * 100.0} %")


if batch:
    df = pd.DataFrame(batch)
    df.to_parquet(str(SAVE_PATH.parent / f"part_{batch_id:05}.parquet"), engine="pyarrow")