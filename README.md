# NvFaidx + GenomeIntervalDataset

PyTorch multi-processing safe fasta and bed dataset, adapted from [NVIDIA/bionemo-framework](https://github.com/NVIDIA/bionemo-framework) and [lucidrains/enformer-pytorch](https://github.com/lucidrains/enformer-pytorch)

## Installation
* pre-built binaries available [here](https://github.com/johahi/nvfaidx/releases)
* select the right python version
* `pip install https://github.com/johahi/nvfaidx/releases/download/v0.0.1/nvfaidx-0.0.1-cp39-cp39-linux_x86_64.whl`

## Usage
```python
from nvfaidx import GenomeIntervalDataset
genome_ds = GenomeIntervalDataset(
    bed_file = 'some_bed.bed',
    fasta_file = 'some_fasta.fa',
    # schema_overrides=[pl.String, pl.Int64,pl.Int64], (required if case the bed file chromosomes are oddly named)
    context_length = 384, # automatically pads or crops sequences to desired length
    return_seq_indices = False # returns one-hots
    )
````
In case `return_seq_indices = True`, maps
```
A : 1
C : 2
G : 3
T : 4
N : 5
. : 6
```