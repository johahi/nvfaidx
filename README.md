# BioNeMo2 Repo
To get started, please build the docker container using
```bash
./launch.sh build
```

All `bionemo2` code is partitioned into independently installable namespace packages. These live under the `sub-packages/` directory.


# TODO: Finish this.

## Devloping with nemo+megatron+bionemo
```
export NEMO_HOME=path/to/local/nemo
export MEGATRON_HOME=path/to/local/megatron
./launch.sh dev
```
The above will make a `.env` file that you can edit as needed to get more variables into the container.

## Models
### Geneformer
#### Get test data for geneformer
```bash
mkdir -p /workspace/bionemo2/data
aws s3 cp \
  s3://general-purpose/cellxgene_2023-12-15_small \
  /workspace/bionemo2/data/cellxgene_2023-12-15_small \
  --recursive \
  --endpoint-url https://pbss.s8k.io
```
#### Running
```bash
NVTE_APPLY_QK_LAYER_SCALING=1 \
  python scripts/singlecell/geneformer/pretrain.py \
    --data-dir /workspace/bionemo2/data/cellxgene_2023-12-15_small/processed_data \
    --num-gpus 1 \
    --num-nodes 1
```