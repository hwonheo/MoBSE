#!/usr/bin/env python3
"""이미 있는 분할 디렉터리에 `external_folds.json` 만 추가한다 — 결정 17.

잠긴 release 의 `folds.json` 은 덮어쓸 수 없으므로 `split` 을 다시 돌리지 않는다.
같은 subjects manifest·config 로 `build_folds` 를 재계산해 기존 split_hash 를
재현하는지 확인한 뒤, 외부 최종 선택용 main pool 3-fold (계획서 §4-3 seed
20262000) 를 새 파일로만 쓴다. 기존 파일은 바이트 단위로 그대로 둔다.

Usage:
    python scripts/h197/26_write_external_folds.py \
        --config configs/redesign_v1/main.yaml \
        --subjects $D/derivatives_v3/cohort_piop1_p7/subjects.jsonl \
        --splits-dir $D/derivatives_v3/splits_piop1_p7
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mobse.v2 import cli                                           # noqa: E402


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--subjects", required=True, type=Path)
    ap.add_argument("--splits-dir", required=True, type=Path)
    args = ap.parse_args(argv[1:])
    try:
        result = cli.run_external_split({"config": str(args.config),
                                         "subjects": str(args.subjects),
                                         "output_dir": str(args.splits_dir)})
    except cli.CLIError as exc:
        print(f"실패: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
