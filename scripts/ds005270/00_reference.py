"""Step 0 (once): build the reference grids for the pilot.

- atlas_grid_master.nii.gz: int16 copy of the locked Schaefer-100 2009cAsym
  2 mm atlas (labels verified identical); AFNI space label set to
  MNI_2009c_asym. Used as -volreg_warp_master and for ROI extraction.
- tpl_bmask_2mm.nii.gz / tpl_brain_2mm.nii.gz: AFNI MNI152_2009 SSW template
  brain mask (NN) and skull-off brain (linear) on the atlas grid, for QC only.

Usage (clean AFNI env): .venv/bin/python -I scripts/ds005270/00_reference.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

import nibabel as nib  # noqa: E402
import numpy as np  # noqa: E402

TEMPLATE = "/Users/hwon/abin/MNI152_2009_template_SSW.nii.gz"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def main() -> int:
    cfg = common.load_config()
    ref = common.REPO / cfg["pilot"]["derivatives_root_rel"] / "reference"
    ref.mkdir(parents=True, exist_ok=True)
    atlas_p = common.REPO / cfg["preprocessing"]["atlas"]["file_rel"]
    if common.sha256_file(atlas_p) != cfg["preprocessing"]["atlas"]["sha256"]:
        print("atlas sha256 mismatch", file=sys.stderr)
        return 1
    src = nib.load(atlas_p)
    lab = np.asarray(src.dataobj)
    out = nib.Nifti1Image(lab.astype(np.int16), src.affine)
    out.header.set_qform(src.affine, code=4)
    out.header.set_sform(src.affine, code=4)
    master = ref / "atlas_grid_master.nii.gz"
    nib.save(out, master)
    back = np.asarray(nib.load(master).dataobj)
    if not np.array_equal(back.astype(np.int64), lab.astype(np.int64)):
        print("int16 atlas copy differs", file=sys.stderr)
        return 1
    run(["3drefit", "-space", "MNI_2009c_asym", str(master)])
    if not np.array_equal(np.asarray(nib.load(master).dataobj).astype(np.int64), lab.astype(np.int64)):
        print("atlas labels changed after 3drefit", file=sys.stderr)
        return 1
    run(["3dresample", "-overwrite", "-master", str(master), "-rmode", "NN",
         "-input", f"{TEMPLATE}[3]", "-prefix", str(ref / "tpl_bmask_2mm.nii.gz")])
    run(["3dresample", "-overwrite", "-master", str(master), "-rmode", "Li",
         "-input", f"{TEMPLATE}[0]", "-prefix", str(ref / "tpl_brain_2mm.nii.gz")])
    labels = sorted(int(v) for v in np.unique(lab) if v != 0)
    common.write_json(ref / "reference.json", {
        "atlas_source_sha256": cfg["preprocessing"]["atlas"]["sha256"],
        "labels": [labels[0], labels[-1], len(labels)],
        "files": {p.name: common.sha256_file(p) for p in sorted(ref.glob("*.nii.gz"))},
        "template": TEMPLATE, "template_sha256": common.sha256_file(Path(TEMPLATE)),
        "note": "sha256 of AFNI-written files can change with AFNI history; labels are checked by value"})
    print("reference ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
