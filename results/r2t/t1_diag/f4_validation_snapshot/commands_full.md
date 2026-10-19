# F4 검증 실행 명령 전문 (결정 88, 합성 자료만)

2026-10-17 10:35:39 KST 에 아래 다섯 명령을 tmux 세션 5 개 (r2t_v4a–e) 로 동시에 실행했다. 저장소 루트에서, 이 폴더의 고정 사본 스크립트를 직접 불렀다 (스크립트의 ROOT = 이 폴더 → 이 폴더의 configs 를 읽음). 환경은 `environment.json`, 해시는 `frozen_sha256.txt`.

```bash
cd /Users/hwon/projects/Git/Manuscript/MoBSE
export OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1
S=results/r2t/t1_diag/f4_validation_snapshot/scripts/r2t
D=results/r2t/t1_diag
.venv/bin/python -B $S/eval_t1_worlds.py --method t1_reg4 --worlds pos:11001 pos:11002 pos:11003 pos:11004 pos:11005 null:11101 null:11102 null:11103 null:11104 null:11105 wrong:11201 wrong:11202 wrong:11203 wrong:11204 wrong:11205 --tag 'validation (F4)' --out $D/val4_old.json 2> $D/val4_old.log
.venv/bin/python -B $S/eval_t1_hard.py --method t1_reg4 --worlds sep=0.3:11301 sep=0.3:11302 sep=0.3:11303 sep=0.3:11304 sep=0.3:11305 ns=1:11401 ns=1:11402 ns=1:11403 ns=1:11404 ns=1:11405 sep=0.3,wrong=1:11501 sep=0.3,wrong=1:11502 sep=0.3,wrong=1:11503 sep=0.3,wrong=1:11504 sep=0.3,wrong=1:11505 --tag 'validation (F4)' --out $D/val4_sep.json 2> $D/val4_sep.log
.venv/bin/python -B $S/eval_t1_hard.py --method t1_reg4 --worlds dwell=8,phase=random:11601 dwell=8,phase=random:11602 dwell=8,phase=random:11603 dwell=8,phase=random:11604 dwell=8,phase=random:11605 dwell=8,phase=random,wrong=1:11701 dwell=8,phase=random,wrong=1:11702 dwell=8,phase=random,wrong=1:11703 dwell=8,phase=random,wrong=1:11704 dwell=8,phase=random,wrong=1:11705 --tag 'validation (F4)' --out $D/val4_dwell8.json 2> $D/val4_dwell8.log
.venv/bin/python -B $S/eval_t1_hard.py --method t1_reg4 --worlds rho=0.9:11801 rho=0.9:11802 rho=0.9:11803 rho=0.9:11804 rho=0.9:11805 rho=0.9,wrong=1:11851 rho=0.9,wrong=1:11852 rho=0.9,wrong=1:11853 rho=0.9,wrong=1:11854 rho=0.9,wrong=1:11855 --tag 'validation (F4)' --out $D/val4_rho.json 2> $D/val4_rho.log
.venv/bin/python -B $S/eval_t1_hard.py --method t1_reg4 --worlds dwell=15,phase=random:11901 dwell=15,phase=random:11902 dwell=15,phase=random:11903 dwell=15,phase=random:11904 dwell=15,phase=random:11905 sep=0.2:11951 sep=0.2:11952 sep=0.2:11953 sep=0.2:11954 sep=0.2:11955 sep=0.1:11981 sep=0.1:11982 sep=0.1:11983 sep=0.1:11984 sep=0.1:11985 --tag 'validation (F4) · 경계 기술값' --out $D/val4_bnd.json 2> $D/val4_bnd.log
```

다시 계산할 때는 `D` 를 새 폴더로 바꾼다 (스크립트는 이미 있는 출력 파일을 덮어쓰지 않고 거부한다). 결과는 결정론적이다 (seed 고정 — F1 보존본에서 한 세계를 다시 계산해 동일함을 확인, F4 는 사용자 지시로 다시 계산하지 않았다).

## 보존 범위
- 보존: 판마다 방법별 31 명 평균 NMSE · Δ (점추정 · 95 % CI) · 기전 보조 · 판정 플래그 · fold 별 선택값 (BEST · EM a · λ · τ · h) · fallback · 실패 수 · 시간 (`val4_*.json`, 로그, partial jsonl).
- **보존 안 함** (생성기 + seed 로 재생성해야 함): Δ 의 사람 간 SD (정정 — 65 행 모두 `delta_sd` null, 파이프라인 키 `delta_sd_all` 을 평가 스크립트가 읽지 않음), 사람별 · fold 별 NMSE, 생성 시계열, mask 색인 목록, inner 명단, 후보별 inner 점수.
