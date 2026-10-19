# 실행 명령 전문 (manifest.json `commands` 의 보충 — manifest 는 바꾸지 않음)

manifest 의 T1 항목 "(같은 15 개)" 를 실제 인자 전체로 푼 판. 검증 당시 실제로 실행한 명령은 아래 두 줄이다 (저장소 루트에서, 당시 `scripts/r2t/eval_t1_worlds.py` = sha `cad9c3379a7c`).

```bash
cd /Users/hwon/projects/Git/Manuscript/MoBSE
export OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.
# F1 (t1_reg)
.venv/bin/python -B scripts/r2t/eval_t1_worlds.py --method t1_reg --worlds pos:9001 pos:9002 pos:9003 pos:9004 pos:9005 null:9101 null:9102 null:9103 null:9104 null:9105 wrong:9201 wrong:9202 wrong:9203 wrong:9204 wrong:9205 --tag validation --out results/r2t/t1_diag/val_reg_r100_n31.json 2>&1 | tee results/r2t/t1_diag/val_reg_r100_n31.log
# 승인판 참고 (t1) — 같은 시각 백그라운드로 실행
.venv/bin/python -B scripts/r2t/eval_t1_worlds.py --method t1 --worlds pos:9001 pos:9002 pos:9003 pos:9004 pos:9005 null:9101 null:9102 null:9103 null:9104 null:9105 wrong:9201 wrong:9202 wrong:9203 wrong:9204 wrong:9205 --tag "validation (승인판 참고)" --out results/r2t/t1_diag/val_t1_r100_n31.json 2> results/r2t/t1_diag/val_t1_r100_n31.log
```

보존본으로 다시 계산할 때 (출력은 새 경로, 기존 결과를 덮어쓰지 않음 — 스크립트가 기존 출력 파일이 있으면 거부함):

```bash
cd /Users/hwon/projects/Git/Manuscript/MoBSE
export OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1
S=results/r2t/t1_diag/f1_validation_snapshot
OUT=<새 폴더>   # 예: 세션 scratchpad
.venv/bin/python -B $S/scripts/r2t/eval_t1_worlds.py --method t1_reg --worlds pos:9001 pos:9002 pos:9003 pos:9004 pos:9005 null:9101 null:9102 null:9103 null:9104 null:9105 wrong:9201 wrong:9202 wrong:9203 wrong:9204 wrong:9205 --tag "보존본 재계산" --out $OUT/val_reg_r100_n31.json
.venv/bin/python -B $S/scripts/r2t/eval_t1_worlds.py --method t1 --worlds pos:9001 pos:9002 pos:9003 pos:9004 pos:9005 null:9101 null:9102 null:9103 null:9104 null:9105 wrong:9201 wrong:9202 wrong:9203 wrong:9204 wrong:9205 --tag "보존본 재계산 (승인판 참고)" --out $OUT/val_t1_r100_n31.json
```
