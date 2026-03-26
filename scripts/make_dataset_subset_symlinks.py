from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description="Create a symlinked dataset-specific subset directory from a combined timeseries root")
    ap.add_argument("--source-dir", required=True, help="Combined timeseries node directory, e.g. data/.../timeseries/100")
    ap.add_argument("--out-dir", required=True, help="Subset output directory")
    ap.add_argument("--prefix", required=True, help="Subject directory prefix to select, e.g. ds000030_")
    args = ap.parse_args()

    source_dir = Path(args.source_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for subject_dir in sorted(source_dir.iterdir()):
        if not subject_dir.is_dir():
            continue
        if not subject_dir.name.startswith(args.prefix):
            continue
        link_path = out_dir / subject_dir.name
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        link_path.symlink_to(subject_dir.resolve(), target_is_directory=True)
        count += 1

    print(f"created_symlinks={count}")


if __name__ == "__main__":
    main()
