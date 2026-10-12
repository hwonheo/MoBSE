#!/bin/bash
# I1 사전 점검 — 공개 뇌 그래프 모델 1 fit 실측 (2026-10-02 승인).
#
# * 저장소는 복사본에서만 돌리고 원본 clone 은 건드리지 않는다.
# * 모델은 하나씩 순서대로 돈다 (GPU 를 서로 나눠 쓰지 않게).
# * GPU 메모리는 venv-i1 에서 뜬 프로세스만 센다. 같은 시각의 외부 GPU 작업 수도 함께 남긴다
#   (외부 작업이 돌면 벽시계가 길게 나올 수 있다).
# * 호환 수정 (복사본에만, 계산 불변): torch>=2.0 의 TransformerEncoderLayer 가 `_sa_block` 에
#   `is_causal` 을 넘기는데 BNT 의 덮어쓴 `_sa_block` 이 받지 않는다 — 그 인자를 받아 버리게 한다.
#
# Usage (h197): OUT=<dir> [ONLY="name name"] bash scripts/i1/probe_models.sh
set -u
D=/mnt/data/mp2026/MoBSE_dataset; V=$D/venv-i1; R=$D/i1/repos
O=${OUT:?OUT 를 주어야 한다}
NPY=$D/i1/data/abide_noglobal_braingb/abide.npy
PY=$V/bin/python
mkdir -p "$O"; touch "$O/results.log"
export WANDB_MODE=disabled PYTHONDONTWRITEBYTECODE=1 HYDRA_FULL_ERROR=1

gpu_watch () {
  while true; do
    local ours=0 ext=0 pid mem
    while IFS=, read -r pid mem; do
      pid=${pid// /}; mem=${mem// /}
      [ -z "$pid" ] && continue
      if tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -q venv-i1; then
        ours=$((ours + mem))
      else
        ext=$((ext + 1))
      fi
    done < <(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits)
    echo "$ours $ext"
    sleep 1
  done
}

COMPAT_SA='grep -rl "def _sa_block" source | xargs sed -i "s/key_padding_mask: Optional\[Tensor\]) -> Tensor:/key_padding_mask: Optional[Tensor], is_causal: bool = False) -> Tensor:/"; grep -rn "is_causal: bool = False" source | wc -l > ../compat_patch_lines.txt'

run () {  # $1=name $2=repo $3=timeout(min) $4..=command (복사본 안에서)
  local name=$1 repo=$2 tmo=$3; shift 3
  if [ -n "${ONLY:-}" ] && [[ " $ONLY " != *" $name "* ]]; then unset PREP; return 0; fi
  local W=$O/$name
  rm -rf "$W"; mkdir -p "$W"; cp -r "$R/$repo" "$W/repo"
  if [ -n "${PREP:-}" ]; then (cd "$W/repo" && eval "$PREP"); fi
  gpu_watch > "$W/gpu.txt" & local gw=$!
  local t0 t1 rc
  t0=$(date +%s.%N)
  (cd "$W/repo" && /usr/bin/time -v timeout "${tmo}m" "$@" > "$W/run.log" 2> "$W/run.err"); rc=$?
  t1=$(date +%s.%N); kill $gw 2>/dev/null; wait $gw 2>/dev/null
  local rss gmax extmax extfrac
  rss=$(grep "Maximum resident" "$W/run.err" | awk '{print $NF}')
  gmax=$(awk '{print $1}' "$W/gpu.txt" | sort -n | tail -1)
  extmax=$(awk '{print $2}' "$W/gpu.txt" | sort -n | tail -1)
  extfrac=$(awk '{n++; if ($2 > 0) e++} END {printf "%.2f", (n ? e / n : 0)}' "$W/gpu.txt")
  printf '{"name":"%s","rc":%s,"wall_s":%.1f,"max_rss_mib":%s,"gpu_max_mib":%s,"timeout_min":%s,"ext_gpu_procs_max":%s,"ext_gpu_time_frac":%s}\n' \
    "$name" "$rc" "$(echo "$t1 - $t0" | bc)" $(( ${rss:-0} / 1024 )) "${gmax:-0}" "$tmo" "${extmax:-0}" "${extfrac:-0}" \
    | tee -a "$O/results.jsonl"
  unset PREP
}

echo "START $(date -u +%FT%TZ) npy_sha=$(sha256sum "$NPY" | cut -c1-16) torch=$($PY -c 'import torch;print(torch.__version__)')" | tee -a "$O/results.log"

PREP=$COMPAT_SA
run bnt BrainNetworkTransformer 60 $PY -m source dataset=ABIDE model=bnt repeat_time=1 dataset.path=$NPY training.epochs=200 preprocess=mixup datasz=100p
run brainnetcnn BrainNetworkTransformer 60 $PY -m source dataset=ABIDE model=brainnetcnn repeat_time=1 dataset.path=$NPY training.epochs=200 preprocess=mixup datasz=100p
# BQN: --runs 는 타입 없는 인자라 명령줄로 넘기면 range("1") 에서 실패한다 — 기본 5 회를 돌고 5 로 나눈다.
PREP="mkdir -p ../data && ln -s $NPY ../data/abide.npy && ln -s \$(pwd) ../BQN_Demo"
run bqn BQN-demo 60 env PYTHONPATH=.. $PY main.py --data_dir ../data --root_path .
PREP="mkdir -p examples/datasets/ABIDE && cp $NPY examples/datasets/ABIDE/abide.npy"
run braingb_gcn_concat BrainGB 45 $PY -m examples.example_main --dataset_name ABIDE --pooling concat --gcn_mp_type edge_node_concate --hidden_dim 256 --repeat 1
PREP="mkdir -p examples/datasets/ABIDE && cp $NPY examples/datasets/ABIDE/abide.npy"
run braingb_gcn_mean BrainGB 45 $PY -m examples.example_main --dataset_name ABIDE --pooling mean --gcn_mp_type edge_node_concate --hidden_dim 256 --repeat 1
# Han: 저장소가 미리 있다고 가정하는 결과 폴더를 만들어 준다 (없으면 분할 저장에서 OSError).
PREP="$COMPAT_SA; mkdir -p exp_results/split_with_valid"
run han_dual RethinkingBCA 90 $PY -u -m source --multirun datasz=100p model=mixed_model dataset=ABIDE repeat_time=1 preprocess=mixup training.epochs=100 dataset.path=$NPY dataset.measure=Autism dataset.node_feature_type=learnable_time_series "model.pooling=[False,False]" "model.sizes=[200,100]" model.dim_reduction=False exp_name=dual_pathway_abide model.one_layer_fc=True dataset.only_positive_corr=True dataset.sparse_ratio=1 dataset.feature_orig_or_sparse=orig dataset.binary_sparse=True dataset.time_series_hidden_size=32 dataset.time_series_encoder=cnn dataset.node_feature_dim=32 dataset.gnn_hidden_channels=32 dataset.gnn_num_layers=1 model.has_nonaggr_module=True model.nonaggr_type=input model.has_aggr_module=True model.aggr_module=gat model.aggr_combine_type=concat "tune_new_learning_rates=[[1.0e-4,1.0e-5]]" dataset.plot_figures=False "dataset.tune_gnn_num_layers=[2]" dataset.batch_size=16 "tune_combine_learning_rates=[[1.0e-4,1.0e-5]]" pretrain_lower_epoch=50 pretrain_nonaggr_coef=1 nonaggr_coef=1 "dataset.tune_gnn_hidden_channels=[32]" save_mlp_weight=False draw_heatmap=False new_weight_decay=1.0e-4
echo "DONE $(date -u +%FT%TZ)" | tee -a "$O/results.log"
