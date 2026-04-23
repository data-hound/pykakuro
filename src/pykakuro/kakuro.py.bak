#!/usr/bin/env python
# -*- coding: utf-8 -*-

# pykakuro - Kakuro Tools For Python
# Copyright (C) 2010 Brandon Thomson <brandon.j.thomson@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
#
# Various options affect the solving routines:

BRUTE_FORCE_WARN_LIMIT = 5*10**5

DEBUG = True

#############################################################################

import copy
import itertools
import logging
import math
import operator
import random
import thread
import threading
import cPickle

from itertools import combinations, chain, izip
from itertools import product as i_product
from pprint import pprint

from collections import Counter

try:
  with open('.set_cache', 'r') as f:
    get_set_cache = cPickle.load(f)
except IOError:
  logging.warning(".set_cache file not found... solving will be slow until "
                  "necessary get_set() entries are generated.")
  get_set_cache = {}

if DEBUG:
  logging.basicConfig(level=logging.DEBUG)
else:
  logging.basicConfig(level=logging.INFO)

def product(lst):
  return reduce(operator.mul, lst)

class MalformedPuzzleException(Exception):
  """The puzzle was not a valid Kakuro puzzle."""

class ConstraintWithoutEntryCellException(MalformedPuzzleException):
  """If there's a constraint in a particular direction, there must be at least
  one entry cell immediately following the constraint in that direction."""

class InvalidPuzzleDataException(MalformedPuzzleException):
  """Found an unexpected object in the puzzle data. Puzzle data should be a
  list consisting of either integers or tuples of two integers."""

class InvalidPuzzleDataLengthException(MalformedPuzzleException):
  """Kakuro puzzles must be square, but the puzzle was not square."""

class SolutionInvalidException(Exception):
  """Raised by check_solution() if the solution is invalid."""

class SolutionInvalidSumException(SolutionInvalidException):
  """Raised by check_solution() if a sum is invalid."""

class SolutionUnsolvedException(SolutionInvalidException):
  """Raised by check_solution() if no attempt was made to solve the puzzle."""

class SolutionNonUniqueException(SolutionInvalidException):
  """Raised by check_solution() if a row/col has the correct sum but the
  numbers are not unique and the puzzle was specified as an exclusive
  puzzle."""

class SolutionRangeException(SolutionInvalidException):
  """Raised by check_solution() if a solution value was outside the range
  allowed by the puzzle (the default range is 1 to 9)."""

class SearchTimeExceeded(Exception):
  """Raised by the solver if the puzzle solution time has exceeded
  a user-specified Timeout."""

class Cell(object):
  """Represents a single cell inside a Kakuro puzzle.

  Generally we only use these when we want to repesent a cell with an unknown
  state during the solving process. After the puzzle has been completely solved
  we only care about the value of the cell."""
  def __init__(self, start=None):
    if start == None:
      start = [1,2,3,4,5,6,7,8,9]
    if type(start) == type(0):
      start = [start]
    self.set = set(start)
    self.test = 0

  def __repr__(self):
    try:
      return "<%s>" % ("".join(str(x) for x in sorted(self.set)))
    except AttributeError:
      return "<%d>" % self.test

class Solution(object):
  """Represents a single solution to a Kakuro puzzle."""

  def get_html(self):
    """Generates an HTML representation of this solution."""

  def get_svg(self):
    """Generates an SVG representation of this solution."""

  def get_txt(self):
    """Generates a plain text representation of this solution."""
    return pretty_print(self.data, self.puzzle.x_size)

  def __init__(self, puzzle, data):
    self.puzzle = puzzle
    self.data = tuple(data)

  def __str__(self):
    return '<Kakuro solution at %s>' % (hex(id(self)))

class Kakuro(object):
  """Creates a new Kakuro puzzle.

  Parameters (max_val, is_exclusive, etc) should not change after a puzzle is
  created."""
  def __str__(self):
    return '<%dx%d Kakuro puzzle, %s, at %s>' % (
            self.x_size,
            len(self.data)/self.x_size,
            "solved" if self.is_solved else "unsolved",
            hex(id(self)),
        )

  def __iter__(self):
    return self._next_solution(has_timeout=False)

  def __init__(self, x_size, data, min_val=1, max_val=9, is_exclusive=True):
    self.data = data

    # No solutions yet
    self.solutions = []

    self.x_size = x_size
    if x_size < 1:
      raise ValueError("x_size must be greater than 0.")

    self.min_val = min_val
    if max_val < min_val:
      raise ValueError("max_val must be greater than or equal to min_val.")

    self.max_val = max_val
    self.is_exclusive = is_exclusive
    self.is_solved = False

    self.num_entry_squares = (
      sum(1 for c in self.data if type(c) == type(0) and c > 0)
    )

    val_size = self.max_val - self.min_val + 1
    self.search_space_size = val_size**self.num_entry_squares

    logging.debug(
      "Puzzle search space size: %d^%d",
      val_size,
      self.num_entry_squares,
    )

  def solve(self, timeout=None, timeout_exception=True):
    """Attempts to find all possible solutions for this puzzle.

    If a timeout (number of seconds) is provided, will raise an exception if
    the puzzle is not yet solved after that amount of time. If
    timeout_exception is set to False, will return False instead of raising an
    exception.

    If a timeout occurs, the puzzle will be the same as it was before solving.
    TODO: Make this true!
    """
    if timeout:
      def interrupt():
        if not t.done:
          thread.interrupt_main()
      t = threading.Timer(timeout, interrupt)
      t.daemon = True
      t.done = False
      t.start()

    try:
      self._solve(bool(timeout))
      self.is_solved = True
      self.speedup = self.search_space_size / self.brute_force_size
      self.difficulty = (0.05 * math.log(self.brute_force_size) +
                         0.01 * self.num_entry_squares)
      if timeout:
        t.done = True
      return True
    except KeyboardInterrupt:
      # Usually we would prefer to raise an exception, but for the
      # multiprocessing module we need to always return a value or the chain
      # will get stuck.
      if timeout_exception:
        raise SearchTimeExceeded()
      else:
        return False

  def get_html(self):
    """Generates HTML representation of unsolved puzzle."""

  def get_svg(self):
    """Generates SVG representation of unsolved puzzle."""

  def get_txt(self):
    """Generates plain text representation of unsolved puzzle."""
    return pretty_print(self.data, self.x_size)

  def _next_solution(self, has_timeout):
    x_size = self.x_size

    data = [Cell() if x==1 else x for x in self.data]

    def is_entry_square(cell):
      return isinstance(cell, Cell)

    constraints = _generate_constraints(data, x_size, is_entry_square)
    _first_run(constraints)

    unsat_constraints = list(constraints)

    # Even complex puzzles rarely require more than 40 passes, but we'll give
    # it up to 100 before we give up and brute force
    for i in xrange(1, 100):
      logging.debug("Starting constraint pass %d", i)

      for sum_val, cells in unsat_constraints:
        if self.is_exclusive:
          _prune_by_count(cells)
        _remove_invalid_sums(cells, sum_val, i)

      logging.debug("Constraint pass %d finished.", i)

      if is_solved(constraints):
        logging.debug("Solved in constraint eval phase after %d passes", i)
        self.brute_force_size = 1
        yield Solution(self, (x.set.copy().pop() if isinstance(x, Cell) else x for x in data))
        return

      unsat_constraints = [c for c in unsat_constraints if any(len(x.set) > 1 for x in c[1])]

      if DEBUG:
        logging.debug("%d/%d constraints still unsatisfied",
                      len(unsat_constraints), len(constraints))
        logging.debug("Remaining search size: %e", _search_space_size(unsat_constraints))

    # Was unable to constrain solution space to one solution, must brute force
    # now
    logging.debug("Brute forcing remaining possibilities")

    brute_cells = set()

    for _, cells in unsat_constraints:
      for cell in cells:
        try:
          count = len(cell.set)
        except AttributeError:
          # Only one possibility which was already removed by another
          # constraint
          pass
        else:
          if count == 1:
            # Only one possibility, so .test value is fixed
            # (this is the most common outcome)
            cell.test = cell.set.pop()
            del cell.set
          elif count > 1:
            # multiple possibilities: add this cell to brute_cells
            brute_cells.add(cell)
          elif count == 0:
            # Cell has no possible values so there is no solution

            # TODO: Eventually this should be just "return"... exception should be
            # raised by solve()
            raise Exception("No values")

    #pprint(unsat_constraints)

    #raise Exception()

    brute_force_size = product(len(cell.set) for cell in brute_cells)
    logging.debug("Brute force search size: %d" % brute_force_size)

    self.brute_force_size = brute_force_size

    # If there is no timeout this is probably running interactively and we
    # should warn the user.
    if brute_force_size > BRUTE_FORCE_WARN_LIMIT and not has_timeout:
      logging.warning("Brute force size of %d is very high", brute_force_size)

    # Make sure order of cells is well-defined
    brute_cells = list(brute_cells)

    # For every cell with more than one possibility, try _all_ values.
    for seq in itertools.product(*(list(c.set) for c in brute_cells)):
      for cell, cell_val in zip(brute_cells, seq):
        cell.test = cell_val
      if _are_constraints_satisfied(unsat_constraints, self.is_exclusive):
        logging.debug("Brute force found solution")
        yield Solution(self, (x.test if isinstance(x, Cell) else x for x in data))

  def _solve(self, has_timeout):
    # TODO: not solving is_exclusive=False puzzles correctly

    if self.is_solved:
      raise Exception("Already solved")

    for solution in self._next_solution(has_timeout):
      self.solutions += [solution]

  def unsolve(self):
    """Removes the solution data from this puzzle leaving the constraints
    intact."""
    self.is_solved = False

    d = self.data
    for i in range(len(d)):
      if d[i] and type(d[i]) != type(()):
        d[i] = 1

  def check_solutions(self):
    for solution in self.solutions:
      self.check_solution(solution)

  def check_solution(self, data):
    """
    Algorithmically verifies that a particular solution is correct. Raises an
    exception if the solution is invalid.
    """

    def is_entry_square(cell):
      return cell != 0 and type(cell) == type(1)

    def fail_debug():
      logging.debug("failed puzzle data:\n" + str(self))

    constraints = _generate_constraints(data, self.x_size, is_entry_square)

    # TODO: better error reporting for all of these
    if not all(val == sum(cells) for val,cells in constraints):
      raise SolutionInvalidSumException()

    if self.is_exclusive:
      if not all(len(cells) == len(set(cells)) for _,cells in constraints):
        fail_debug()
        raise SolutionNonUniqueException()

    if any(any(cell > self.max_val for cell in cells) for _,cells in constraints):
      fail_debug()
      raise SolutionRangeException()

    if any(any(cell < self.min_val for cell in cells) for _,cells in constraints):
      fail_debug()
      raise SolutionRangeException()

  def check_puzzle(self):
    """Raises an exception if puzzle is not valid."""
    if len(self.data) % self.x_size != 0:
      raise InvalidPuzzleDataLengthException("The input data must be square in shape.")

    for x in self.data:
      if (type(x) != type(0)) and (type(x) != type(())):
        raise InvalidPuzzleDataException("Only tuples and integers are allowed in "
                                         "the input.")

    def is_entry_square(cell):
      return cell != 0

    # TODO: for some reason this function modifies the first arg passed; fix
    # it so it doesn't and then the deepcopy can be removed.
    constraints = _generate_constraints(copy.deepcopy(self.data), self.x_size, is_entry_square)

    if any(len(cells) < 1 for _,cells in constraints):
      raise ConstraintWithoutEntryCellException("Constraint without entry square.")

def pretty_print(data, x_size):
  """Draws a prettier version of puzzle strings"""
  #_verify_input_integrity(data, x_size)

  strings = []
  for x in data:
    if type(x) == type(()):
      strings.append(','.join(str(y) for y in x))
    else:
      strings.append(str(x))
  cell_width = max(len(x) for x in strings)
  centered = [x.center(cell_width) for x in strings]
  by_row = [centered[z:z+x_size] for z in range(0,len(data)-x_size+1,x_size)]
  separator = '+'.join(["-"*cell_width]*x_size) + '+'
  row_strings = ['|'.join(x)+'|' for x in by_row]
  y=len(row_strings)
  for x in range(y):
    row_strings.insert(y-x, separator)

  return '\n'.join((row_strings))

def is_solved(constraints):
  return all(all(len(x.set) == 1 for x in cells) for _,cells in constraints)

class Success(Exception): pass

def rows_from_list(list, x_size):
  return [list[z:z+x_size] for z in range(0,len(list)-x_size+1,x_size)]

def cols_from_list(list, x_size):
  return [list[z::x_size] for z in range(x_size)]

def _generate_constraints(input, x_size, is_entry_square):
  """
  Creates a list of constraints based on given input. If the input contains
  objects, the objects will be multiply referenced in the output list where
  constraints overlap.

  is_entry_square - a function provided by the caller that returns true if a
  cell provided to the function is a square where a number needs to go. (This
  allows this function to be agnostic of whether objects or simple numbers are
  used in the list.)
  """
  rows = rows_from_list(input, x_size)
  cols = cols_from_list(input, x_size)

  constraints = []
  ACROSS, DOWN = 0, 1

  for row in rows:
    constraints.extend(_process_row_or_col(row, ACROSS, is_entry_square))

  for col in cols:
    constraints.extend(_process_row_or_col(col, DOWN, is_entry_square))

  return constraints

def gen_random(x_size=10, y_size=10, is_solved=True, is_exclusive=True,
               min_val=1, max_val=9, seed=None):
  """Generates a new random Kakuro puzzle of the specified size.  If a
  ``seed`` is provided, output is deterministic when all other parameters are
  also the same. Providing a seed is recommended."""

  def row(a, x_size, n):
    return a[x_size*n:x_size*(n+1)]

  def col(a, x_size, n):
    return a[n:len(a):x_size]

  if seed:
    random.seed(seed)

  #s = random.sample(range(1,10),9)

  a=[0]*x_size*y_size

  for idx in range(x_size*y_size):
    row_idx = idx/x_size
    col_idx = idx%x_size
    if random.random() > 0.6:
      # TODO: This works OK for small boards, but not for big ones
      for _ in range(20):
        val = random.randint(min_val, max_val)
        if is_exclusive:
          if (val not in row(a, x_size, row_idx) and
              val not in col(a, x_size, col_idx)):
            a[idx] = val
            break
        else:
          a[idx] = val
          break

  # 0-out top and left
  a[0:x_size] = (0,)*x_size
  a[0::x_size] = (0,)*y_size

  # add tuples and right rules
  sum = 0
  for y in range(0, y_size):
    for i in range(x_size + y*x_size-1, y*x_size-1, -1):
      if a[i]:
        sum += a[i]
      elif sum:
        a[i] = sum, 0
        sum = 0

  # add tuples and down rules; modify existing tuples if necessary
  sum = 0
  for x in range(0, x_size):
    for i in range(len(a) - x_size + x, -1, -x_size):
      if a[i] and type(a[i]) != type(()):
        sum += a[i]
      elif sum:
        if type(a[i]) == type(()):
          a[i] = a[i][0], sum
        else:
          a[i] = 0, sum
        sum = 0

  k=Kakuro(x_size, a, min_val, max_val, is_exclusive)
  if not is_solved:
    k.unsolve()

  k.is_solved = is_solved
  return k

def _are_constraints_satisfied(constraints, check_uniq):
  return (_are_constraint_sums_valid(constraints) and
          (_are_vals_unique(constraints) if check_uniq else True))

def _are_constraint_sums_valid(constraints):
  return all(val == sum(c.test for c in cells) for val,cells in constraints)

def _are_vals_unique(constraints):
  for _, cells in constraints:
    vals = [c.test for c in cells]
    if len(vals) != len(set(vals)):
      return False
  return True

def _process_row_or_col(record, row_or_col, is_entry_square):
  """Generates all the constraints from a single row or column.

  record: row or column data
  row_or_col: 0 or 1 depending on whether this is a row or a column
  is_entry_square: function which tells whether this is an answer cell"""
  new_constraints = []

  record = list(reversed(record))
  while record:
    cell = record.pop()
    if type(cell) != type(()):
      continue # Not a constraint cell
    sum_val = cell[row_or_col]
    if sum_val == 0:
      continue # No constraint for this direction
    cell = record.pop()
    if not is_entry_square(cell):
      raise ConstraintWithoutEntryCellException(record)
    cells = [cell]
    while record:
      cell = record.pop()
      if not is_entry_square(cell):
        record.append(cell) #unpop
        break
      cells.append(cell)
    new_constraints.append((sum_val, cells))

  return new_constraints

def get_vals(sum_val, n):
  """
  Returns a tuple of tuples of all the combinations of n integers that sum to
  sum_val.

  >>> get_vals(10, 3)
  ((1, 2, 7), (1, 3, 6), (1, 4, 5), (2, 3, 5))

  >>> get_vals(7, 3)
  ((1, 2, 4))
  """
  return tuple(x for x in combinations(range(1, sum_val),n) if
          sum(x) == sum_val and all(y<10 for y in x))

def flatten(listOfLists):
  return list(chain.from_iterable(listOfLists))

def get_set(sum_val, n):
  """
  Returns the set of integers present in all the combinations of n integers
  that sum to sum_val.

  For a nice colorful table of these results, try:
    http://www.kevinpluck.net/kakuro/KakuroCombinations.html

  >>> get_set(10, 3)
  set(1, 2, 3, 4, 5, 6, 7)

  >>> get_set(7, 3)
  set(1, 2, 4)
  """
  global get_set_cache

  try:
    return get_set_cache[sum_val, n]
  except KeyError:
    pass

  if n == 1:
    # TODO: Should check max_val
    if sum_val < 10:
      s = frozenset((sum_val,))
    else:
      s = frozenset()
  else:
    s = frozenset(flatten(get_vals(sum_val, n)))

  get_set_cache[sum_val, n] = s
  return s

def _generate_set_cache():
  """Generates a lookup table for the get_set() function and pickles it to be
  loaded on future runs. This takes a long time to finish!

  Rather than having end-users build this table we distribute a pre-generated
  table."""
  global get_set_cache

  # This covers all the possibilities for standard 1-9 Kakuro, but wider
  # ranges require a bigger cache.

  # TODO: This only works for is_exclusive=True and assumes a standard spread
  # 1-9.

  # TODO: This is extremely slow... I guess it's not a high priority though
  for sum_val in range(1,46):
    for n in range(1,10):
      get_set(sum_val, n)
      print sum_val, n

  with open('.set_cache', 'w') as f:
    cPickle.dump(get_set_cache, f, cPickle.HIGHEST_PROTOCOL)

def _first_run(constraints):
  """Assigns set of possible values to each cell based on analysis of
  constraint value and number of cells. This is very fast as long as
  get_set_cache is populated.
  """
  for sum_val, cells in constraints:
    s = get_set(sum_val, len(cells))
    for c in cells:
      c.set &= s

def _prune_singles(cells):
  """Given a set of cells, if any cells have only 1 possibility, this
  possibility will be removed from all other cells.

  This is only useful for puzzles where is_exclusive = True.

  This is a special case of _prune_by_count where n=1. It is not needed if
  _prune_by_count is used."""
  for check_cell in cells:
    if len(check_cell.set) == 1:
      for remove_cell in cells:
        if check_cell is not remove_cell:
          remove_cell.set -= check_cell.set;

def _prune_by_count(cells):
  """Given a set of cells, if any subset of n cells have the same n
  possibilities, no other cells in the set can have any of those
  possibilities.

  This is only useful for puzzles where is_exclusive = True.

  Examples:
    [<123>, <123>, <123>, <12345>] -> [<123>, <123>, <123>, <45>]
    [<12>, <12>, <1234>, <12345>] -> [<12>, <12>, <34>, <345>]
  """
  c=Counter()

  for cell in cells:
    c[frozenset(cell.set)] += 1

  if len(c) == 1:
    return # All cells have identical choices, nothing to do

  for src_cells_set, count in c.items():
    if count > len(src_cells_set):
      raise Exception() # No solutions to puzzle!
    if count == len(src_cells_set):
      # We can modify the other cells
      for remove_cell in cells:
        if src_cells_set != remove_cell.set:
          remove_cell.set -= src_cells_set

def _search_space_size(constraints):
  size = 1.0 # Use floating point to avoid slow bignum
  for _, cells in constraints:
    for c in cells:
      size *= len(c.set)
  return size

def _remove_invalid_sums(cells, sum_val, i):
  """Removes any possibilities which have become impossible due to changes in
  other cells.

  Example:
    sum_val = 12
    [<789>, <345789>] -> [<789>, <345>]
  """

  sets = [cell.set for cell in cells]

  # The big list comprehension below is a very expensive computation when
  # there are lots of possibilities for the given set of cells. The cost is
  # something like n_0 * n_1 * n_2 ... where n_0 is the number of
  # possibilities in cell 0, and so on. This block calculates that sum and
  # aborts on sets of cells with big sums when i is small. As i increases,
  # larger checks are allowed. It saves a lot of wasted compute time for most
  # puzzles.
  size = product(len(s) for s in sets)
  if not 1 < size < 1.7**i+500:
    return

  # The reduction work is done in this block. This is an expensive line!
  new_sets = izip(*(seq for seq in i_product(*sets)
                   if sum(seq)==sum_val and len(seq) == len(set(seq))))
  for old, new in izip(cells, new_sets):
    old.set = set(new)
