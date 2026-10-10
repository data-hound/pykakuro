#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Uses multiprocessing pool to generate and test lots of puzzles.
# NOTE: the solver's wall-clock timeout (DISCARD_TIMEOUT) makes `is_exclusive` unreliable on its own. Rows whose solve did not
# finish are kept but flagged (solve_finished=False, is_exclusive=False); so are rows where check_solution raised on the solver's
# output (solution_check_ok=False, is_exclusive=False; in a 60-seed 9x9 smoke test 22 raised "Unfilled entries", although the stored
# master solutions are valid under the independent check, so dropping them would silently change the yield). Uniqueness MUST be established independently before any puzzle is used: see analysis/03_verify_uniqueness.py (OR-Tools
# CP-SAT, counts solutions up to 2) and analysis/09_generate_unique.py (this generator + that gate as the acceptance test).
# BOARD_SIZEs = 5,6,7,8,9,10,11 

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
import argparse

parser = argparse.ArgumentParser()

parser.add_argument("--board_size", type=int, default=11)
parser.add_argument("--start_id", type=int, default=0)
parser.add_argument("--puzzle_count", type=int, default=100000)
parser.add_argument("--workers", type=int, default=POOL_SIZE)
parser.add_argument("--out_dir", default="/hpc/group/tdunn/asabath/ece790_diffusion/Project/ar-diffusion-2d/data/kakuro_mania")

args = parser.parse_args()

BOARD_SIZE = args.board_size
PUZZLE_COUNT = args.puzzle_count
START_ID = args.start_id
POOL_SIZE = args.workers

# SAVE_PATH = Path("/hpc/group/tdunn/asabath/ece790_diffusion/Project/ar-diffusion-2d/data/kakuro") / "kakuro_100k.parquet"
SAVE_PATH = Path(args.out_dir) / "kakuro_mania.parquet"
SAVE_PATH.parent.mkdir(exist_ok=True, parents=True)
set_cache_path = Path('.set_cache')

if not set_cache_path.exists():
  kakuro._generate_set_cache()

def f(i):
  k = kakuro.gen_random(BOARD_SIZE, BOARD_SIZE, seed=i, is_solved=False)
  success = k.solve(timeout=DISCARD_TIMEOUT, timeout_exception=False)
  if success:
    try:
      k.check_solution(k.solutions[0].data)
      return i, k, True, None
    except Exception as e:
      print(f"Got exception {type(e).__name__}, {str(e)} for puzzle w/ seed {i}: \n{k.get_lol()} \nsolution : \n{k.solutions[0].get_lol()}")
      
      if VERBOSE:
        print("="*50)
        print("Traceback: ")
        print(traceback.format_exc())
        print("="*50)
      return i, k, True, e
  else:
    return i, k, False, kakuro.SolutionUnsolvedException('timeout after %s s' % DISCARD_TIMEOUT)

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
  'solve_finished':         [],
  'solution_check_ok':      [],
}

batch = []
batch_size = 10000
# batch_size = 5
batch_id = START_ID // batch_size


num_timeouts = 0
for seed, puzzle, finished, err in pool.imap_unordered(f, list(range(START_ID, START_ID + PUZZLE_COUNT)), 10):
  check_ok = not (finished and err is not None)   # check_solution raised on the solver's output
  if not check_ok:
    num_failures += 1
  if not finished:
    num_timeouts += 1
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
        "is_exclusive": bool(finished and check_ok and puzzle.is_exclusive and len(puzzle.solutions) <= 1),   # only meaningful if the solve finished
        "solve_finished": bool(finished),
        "solution_check_ok": bool(check_ok),
    }

  batch.append(row)

  if len(batch) >= batch_size:
    df = pd.DataFrame(batch)
    df.to_parquet(str(SAVE_PATH.parent / f"board_{BOARD_SIZE}_part_{batch_id:05}.parquet"), engine="pyarrow")
    batch.clear()
    batch_id+=1


  if not finished:
    print("{0}: solve timed out (row kept, solve_finished=False)".format(seed))
  elif puzzle:
    print("{0}: {1} {2}".format(seed, repr(puzzle), puzzle.difficulty))
  else:
    print("{0}: Too complex".format(seed))

print(f"check_solution failures (flagged) = {num_failures/PUZZLE_COUNT * 100.0} %, solver timeouts (flagged) = {num_timeouts/PUZZLE_COUNT * 100.0} %")


if batch:
    df = pd.DataFrame(batch)
    df.to_parquet(str(SAVE_PATH.parent / f"board_{BOARD_SIZE}_part_{batch_id:05}.parquet"), engine="pyarrow")