#!/usr/bin/env bash
# Wave 2 사전 용량 실측 (U26 해소). 다운로드는 하지 않고 목록만 센다.
#
# Wave 1 감사에서 window 설계가 확정된 뒤에만 실행한다. 확정 전에 BOLD 본체를
# 받으면 target native TR 이 0.75초로 밝혀질 경우 설계 변경으로 헛수고가 된다.
#
# 사용: bash 03_wave2_size_probe.sh > wave2_size_probe.txt
set -euo pipefail

S3_BASE="s3://openneuro.org"
TASKS=(restingstate emomatching workingmemory)
SPACE="space-MNI152NLin2009cAsym"

command -v aws >/dev/null || { echo "aws CLI 없음" >&2; exit 3; }

for ds in ds002785 ds002790; do
  echo "=== $ds ==="
  listing=$(mktemp)
  aws s3 ls --no-sign-request --recursive "$S3_BASE/$ds/derivatives/fmriprep/" > "$listing"
  total_bytes=0
  for t in "${TASKS[@]}"; do
    # preproc BOLD + brain mask 만 센다
    read -r n bytes < <(
      awk -v t="task-$t" -v sp="$SPACE" '
        $0 ~ t && $0 ~ sp && $0 ~ /desc-preproc_bold\.nii\.gz$/ { n++; b += $3 }
        END { printf "%d %d\n", n+0, b+0 }' "$listing")
    printf "  %-16s files=%-5s bytes=%-14s  %.1f GiB\n" "$t" "$n" "$bytes" \
      "$(awk -v b="$bytes" 'BEGIN{printf "%.4f", b/1073741824}')"
    total_bytes=$(( total_bytes + bytes ))
  done
  printf "  %-16s %s bytes  %.1f GiB\n" "TOTAL" "$total_bytes" \
    "$(awk -v b="$total_bytes" 'BEGIN{printf "%.4f", b/1073741824}')"
  echo "  (참고) derivative 트리 전체 객체 수: $(wc -l < "$listing")"
  rm -f "$listing"
done

echo
echo "판단 기준: 위 TOTAL 이 h197 의 가용 디스크에 여유 있게 들어가지 않으면"
echo "streaming 추출(subject 단위 다운로드 → ROI 추출 → 원본 삭제)을 설계에 포함한다."
