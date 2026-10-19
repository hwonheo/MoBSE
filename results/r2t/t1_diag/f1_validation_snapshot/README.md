# F1 검증 당시 보존본 (결정 88, 합성 자료만)

- 무엇: F1 (`t1_reg`) 검증 seed 15 개 (pos 9001–9005 · null 9101–9105 · wrong 9201–9205, 100 ROI · 31 명) 를 연 당시의 코드 12 개 · 설정 2 개 · 결과 · 로그.
- 해시: `manifest.json` 의 `files` — 각 파일의 sha256, 검증 전 기록값 (진단 문서 §4, 앞 12 자리), 일치 여부, 저장소 현행 값. **12 개 모두 검증 전 값과 일치.**
- `scripts/r2t/eval_t1_worlds.py` 는 **복원본**이다. 저장소 현행판 (`5f6e52ea1408`) 에서 F2 등록 세 줄 변경을 정확히 되돌렸고, 그 sha 가 검증 전 값 `cad9c3379a7c` 와 일치해서 검증 당시 판으로 표기한다. 실제 이전 파일 사본은 남아 있지 않다.
- 재현: 이 폴더의 `scripts/r2t/eval_t1_worlds.py` 를 직접 부르면 ROOT 가 이 폴더라 이 폴더의 configs 를 읽는다. pos:9001 재계산이 저장 결과와 같음을 확인 (`manifest.json` `reproduction_check`).
- 환경 · 명령: `manifest.json` `environment` · `commands`.
- 이 폴더는 덮어쓰지 않는다. 저장소의 현행 파일 (특히 `eval_t1_worlds.py`) 해시와 혼동하지 말 것.
