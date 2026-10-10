import pandas as pd
from datasets import load_dataset, concatenate_datasets, DatasetDict
import xxhash
from pathlib import Path
import ast

dataset = load_dataset(
    "parquet",
    data_files="/hpc/group/tdunn/asabath/ece790_diffusion/Project/ar-diffusion-2d/data/kakuro_mania/*.parquet",
    split="train"
)

GRID_SIZES = [9, 11, 15]
VAL_SIZE = 5000
TEST_SIZE = 5000
MAX_TRAIN = 50000
MIN_TRAIN = MAX_TRAIN


# ds = load_dataset("apaxdor/kakuro_craze")
save_path = Path("/hpc/group/tdunn/asabath/ece790_diffusion/Project/ar-diffusion-2d/data/kakuro_kraze/")
save_path.mkdir(exist_ok=True, parents=True)

# dataset = concatenate_datasets([
#     ds["train"],
#     ds["validation"],
#     ds["test"]
# ])

dataset = dataset.filter(lambda x: x["is_exclusive"] == True)


def split_grid(ds, grid_size, **kwargs):
    global MIN_TRAIN

    subset = ds.filter(lambda x: x["grid_size"] == grid_size)
    subset = subset.shuffle(seed=42)

    validation = subset.select(range(VAL_SIZE))
    test = subset.select(range(VAL_SIZE, VAL_SIZE + TEST_SIZE))

    train_start = VAL_SIZE + TEST_SIZE
    available_train = len(subset) - train_start

    train_size = available_train

    if train_size < MIN_TRAIN:
        MIN_TRAIN = train_size

    if kwargs.get("max_train") is not None:
        train_size = min(kwargs["max_train"], available_train)

    if kwargs.get("equal_train") is not None:
        train_size = min(kwargs["equal_train"], available_train)

    train = subset.select(range(train_start, train_start + train_size))

    return DatasetDict({
        "train": train,
        "validation": validation,
        "test": test
    })

def split(example, idx):
    r = idx % 100
    if r < 80:
        example["split"] = "train"
    elif r < 90:
        example["split"] = "validation"
    else:
        example["split"] = "test"
    return example

def puzzle_id(example):
    flat = ''.join(str(x) for row in example["solution"] for x in row)
    example["puzzle_id"] = xxhash.xxh64(flat).hexdigest()
    return example

def parse_grid(s):
    s = s.strip()

    # wrap rows if the dataset omitted the outer list
    if not s.startswith("[["):
        s = "[" + s.replace("\n", ",") + "]"

    grid = ast.literal_eval(s)

    return [list(row) for row in grid]

def get_grid_size(example):
    example['grid_size'] = len(parse_grid(example["solution"]))
    return example


dataset = dataset.map(puzzle_id)
dataset = dataset.map(get_grid_size)

# This is not present in the columns of online dataset, but present in columns of local dataset
print("dataset columns = ", dataset.column_names)
columns_to_drop = ["search_space_size", "brute_force_size", "seed"]

print("Removing spurious columns ...", columns_to_drop)
dataset = dataset.remove_columns(columns_to_drop)

datasets_by_grid = {}

for g in GRID_SIZES:
    datasets_by_grid[g] = split_grid(dataset, g, max_train=50000)
    # datasets_by_grid[g].save_to_disk(f"{str(save_path)}/grid{g}")

    ds = split_grid(dataset, g, max_train=50000)

    grid_path = save_path / f"grid{g}"
    grid_path.mkdir(parents=True, exist_ok=True)

    ds["train"].to_parquet(grid_path / "train.parquet")
    ds["validation"].to_parquet(grid_path / "validation.parquet")
    ds["test"].to_parquet(grid_path / "test.parquet")

# dataset = dataset.map(split, with_indices=True)

# train_ds = dataset.filter(lambda x: x["split"] == "train")
# val_ds = dataset.filter(lambda x: x["split"] == "validation")
# test_ds = dataset.filter(lambda x: x["split"] == "test")

# print("train:", len(train_ds))
# print("validation:", len(val_ds))
# print("test:", len(test_ds))

# ds = DatasetDict({
#     "train": train_ds,
#     "validation": val_ds,
#     "test": test_ds
# })

# for split in ["train","validation", "test"]:
#     split_ds = ds[split]
#     total = len(split_ds)
#     count_9 = len(split_ds.filter(lambda x: x["grid_size"] == 9))
#     print("9x9 boards: ",split, 100 * count_9 / total)

#     count_11 = len(split_ds.filter(lambda x: x["grid_size"] == 11))
#     print("11x11 boards: ",split, 100 * count_11 / total)

#     count_15 = len(split_ds.filter(lambda x: x["grid_size"] == 15))
#     print("15x15 boards: ",split, 100 * count_15 / total)

# ds.save_to_disk(save_path)