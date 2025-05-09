# adapted from lucidrains/enformer-pytorch

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset

import polars as pl
import numpy as np
from random import randrange, random, randint
from pathlib import Path
import os

# helper functions

def exists(val):
    return val is not None

def identity(t):
    return t

def cast_list(t):
    return t if isinstance(t, list) else [t]

def coin_flip():
    return random() > 0.5

# genomic function transforms

seq_indices_embed = torch.zeros(256).long()
seq_indices_embed[ord('a')] = 0
seq_indices_embed[ord('c')] = 1
seq_indices_embed[ord('g')] = 2
seq_indices_embed[ord('t')] = 3
seq_indices_embed[ord('n')] = 4
seq_indices_embed[ord('A')] = 0
seq_indices_embed[ord('C')] = 1
seq_indices_embed[ord('G')] = 2
seq_indices_embed[ord('T')] = 3
seq_indices_embed[ord('N')] = 4
seq_indices_embed[ord('.')] = 4 # changed, for it to work with nn.Embedding

one_hot_embed = torch.zeros(256, 4)
one_hot_embed[ord('a')] = torch.Tensor([1., 0., 0., 0.])
one_hot_embed[ord('c')] = torch.Tensor([0., 1., 0., 0.])
one_hot_embed[ord('g')] = torch.Tensor([0., 0., 1., 0.])
one_hot_embed[ord('t')] = torch.Tensor([0., 0., 0., 1.])
one_hot_embed[ord('n')] = torch.Tensor([0., 0., 0., 0.])
one_hot_embed[ord('A')] = torch.Tensor([1., 0., 0., 0.])
one_hot_embed[ord('C')] = torch.Tensor([0., 1., 0., 0.])
one_hot_embed[ord('G')] = torch.Tensor([0., 0., 1., 0.])
one_hot_embed[ord('T')] = torch.Tensor([0., 0., 0., 1.])
one_hot_embed[ord('N')] = torch.Tensor([0., 0., 0., 0.])
one_hot_embed[ord('.')] = torch.Tensor([0.25, 0.25, 0.25, 0.25])

reverse_complement_map = torch.Tensor([3, 2, 1, 0, 4]).long()

def torch_fromstring(seq_strs):
    batched = not isinstance(seq_strs, str)
    seq_strs = cast_list(seq_strs)
    np_seq_chrs = list(map(lambda t: np.fromstring(t, dtype = np.uint8), seq_strs))
    seq_chrs = list(map(torch.from_numpy, np_seq_chrs))
    return torch.stack(seq_chrs) if batched else seq_chrs[0]

def str_to_seq_indices(seq_strs):
    seq_chrs = torch_fromstring(seq_strs)
    return seq_indices_embed[seq_chrs.long()]

def str_to_one_hot(seq_strs):
    seq_chrs = torch_fromstring(seq_strs)
    return one_hot_embed[seq_chrs.long()]

def seq_indices_to_one_hot(t, padding = -1):
    is_padding = t == padding
    t = t.clamp(min = 0)
    one_hot = F.one_hot(t, num_classes = 5)
    out = one_hot[..., :4].float()
    out = out.masked_fill(is_padding[..., None], 0.25)
    return out

# augmentations

def seq_indices_reverse_complement(seq_indices):
    complement = reverse_complement_map[seq_indices.long()]
    return torch.flip(complement, dims = (-1,))

def one_hot_reverse_complement(one_hot):
    *_, n, d = one_hot.shape
    assert d == 4, 'must be one hot encoding with last dimension equal to 4'
    return torch.flip(one_hot, (-1, -2))

# processing bed files

class FastaInterval():
    def __init__(
        self,
        *,
        fasta_file,
        context_length = None,
        return_seq_indices = False,
        shift_augs = None,
        rc_aug = False
    ):
        from .nvfaidx import NvFaidx
        fasta_file = Path(fasta_file)
        assert fasta_file.exists(), 'path to fasta file must exist'
        if os.path.exists(f"{fasta_file}.fai"):
            self.seqs = NvFaidx(str(fasta_file), faidx_path = f"{fasta_file}.fai", ignore_existing_fai = False)
        else:
            self.seqs = NvFaidx(str(fasta_file))
        self.return_seq_indices = return_seq_indices
        self.context_length = context_length
        self.shift_augs = shift_augs
        self.rc_aug = rc_aug

    def __call__(self, chr_name, start, end, return_augs = False):
        interval_length = end - start
        chromosome = self.seqs[chr_name]
        chromosome_length = len(chromosome)

        if exists(self.shift_augs):
            min_shift, max_shift = self.shift_augs
            max_shift += 1

            min_shift = min(max(start + min_shift, 0) - start, 0)
            max_shift = max(min(end + max_shift, chromosome_length) - end, 1)

            rand_shift = randrange(min_shift, max_shift)
            start += rand_shift
            end += rand_shift

        left_padding = right_padding = 0

        if exists(self.context_length) and interval_length != self.context_length:
            extra_seq = self.context_length - interval_length

            extra_left_seq = extra_seq // 2
            extra_right_seq = extra_seq - extra_left_seq

            start -= extra_left_seq
            end += extra_right_seq

        if start < 0:
            left_padding = -start
            start = 0

        if end > chromosome_length:
            right_padding = end - chromosome_length
            end = chromosome_length
        if start > chromosome_length:
            start  = chromosome_length - self.context_length
            right_padding = 0
            left_padding = 0
            end = chromosome_length
        if end < 0:
            start = 0
            end = self.context_length
            right_padding = 0
            left_padding = 0

        seq = ('.' * left_padding) + str(chromosome[start:end]) + ('.' * right_padding)

        should_rc_aug = self.rc_aug and coin_flip()

        if self.return_seq_indices:
            seq = str_to_seq_indices(seq)

            if should_rc_aug:
                seq = seq_indices_reverse_complement(seq)

            return seq

        one_hot = str_to_one_hot(seq)

        if should_rc_aug:
            one_hot = one_hot_reverse_complement(one_hot)

        if not return_augs:
            return one_hot

        # returns the shift integer as well as the bool (for whether reverse complement was activated)
        # for this particular genomic sequence

        rand_shift_tensor = torch.tensor([rand_shift])
        rand_aug_bool_tensor = torch.tensor([should_rc_aug])

        return one_hot, rand_shift_tensor, rand_aug_bool_tensor


class GenomeIntervalDataset(Dataset):
    def __init__(
        self,
        bed_file,
        fasta_file,
        filter_df_fn = identity,
        chr_bed_to_fasta_map = dict(),
        schema_overrides = None,
        context_length = None,
        return_seq_indices = False,
        shift_augs = None,
        rc_aug = False,
        return_augs = False,
        sample_in_frame = False,
    ):
        super().__init__()
        bed_path = Path(bed_file)
        assert bed_path.exists(), 'path to .bed file must exist'

        df = pl.read_csv(str(bed_path), separator = '\t', has_header = False, schema_overrides = schema_overrides)
        df = filter_df_fn(df)
        self.df = df

        # if the chromosome name in the bed file is different than the keyname in the fasta
        # can remap on the fly
        self.chr_bed_to_fasta_map = chr_bed_to_fasta_map

        self.fasta = FastaInterval(
            fasta_file = fasta_file,
            context_length = context_length,
            return_seq_indices = return_seq_indices,
            shift_augs = shift_augs,
            rc_aug = rc_aug
        )
        if context_length is not None:

            def is_valid_interval(row):
                try:
                    chrom_bed = row[0] # Chromosome name from BED file (assuming positional access)
                    start_bed = row[1]
                    end_bed = row[2]

                    chrom_fasta_length = len(self.fasta.seqs[chrom_bed])

                    if chrom_fasta_length is None:
                        print(f"Warning: Chromosome '{chrom_bed}' not found in FASTA lengths.")
                        return False

                    interval_length = end_bed - start_bed
                    is_valid = interval_length <= chrom_fasta_length and context_length <= chrom_fasta_length and start_bed < end_bed and start_bed > 0
                    # print(f"Interval: {chrom_bed}:{start_bed}-{end_bed}, Length: {interval_length}, Chromosome Length: {chrom_fasta_length}, Valid: {is_valid}")
                    return is_valid
                except Exception as e:
                    # print(f"Error processing row: {row}, Error: {e}")
                    return False

            original_length = len(df)
            # print("Creating boolean mask for filtering...")
            bool_mask_list = []
            for row in df.rows(named=False): # Iterate over DataFrame rows as lists
                bool_mask_list.append(is_valid_interval(row)) # Apply is_valid_interval to each row and collect booleans
            valid_interval_mask = pl.Series(bool_mask_list, dtype=pl.Boolean) # Create Polars boolean Series

            # print("Applying filter using boolean mask...")
            self.df = df.filter(valid_interval_mask) # Filter DataFrame using the boolean Serieser with boolean Series
            # print("Filter application complete.")
            print (f"Original dataset size: {original_length}, now: {len(self.df)}")
        self.context_length = context_length
        self.sample_in_frame = sample_in_frame
        self.return_augs = return_augs


    def __len__(self):
        return len(self.df)

    def __getitem__(self, ind):
        interval = self.df.row(ind)
        chr_name, start, end = (interval[0], interval[1], interval[2])
        chr_name = self.chr_bed_to_fasta_map.get(chr_name, chr_name)
        if self.sample_in_frame and end - start > self.context_length:
            start = randint(start, end - self.context_length)
            end = start + self.context_length
        return self.fasta(chr_name, start, end, return_augs = self.return_augs)

