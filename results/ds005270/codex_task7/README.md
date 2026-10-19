# Codex 작업 폴더 (task-7) md 문서 사본

2026-10-19 KST, 사용자 지시 "저장소 밖 codex 작업 폴더의 문서를 여기로 복사" → 선택 TUI "md 문서만" · 위치 `results/ds005270/codex_task7/`.

- 출처: Mac `~/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/` (저장소 밖, iCloud). 원본은 그대로 둔다.
- 범위: 위 폴더의 `*.md` 12 개. 폴더 구조를 그대로 유지했고, 내용은 고치지 않았다.
- 제외한 것:
  - md 가 아닌 파일: json · tsv · log · py · html · 그림 · PDF. provenance 와 전송 기록 (`copy_completed.json` 등) 이 여기에 해당한다. 위치는 `docs/handoff/ds005270_pilot_expansion_on_hold_2026-10-19.md` 의 "기록 파일 위치" 에 적었다.
  - BIDS 사본의 `README.md` (원자료 일부).
  - fMRIPrep 산출 폴더 (`sub-*-run/`) 와 `tmp/` (venv).
- 저장소 문서와 같은 사본 3 개 (바이트 동일, 중복 제거하지 않음):
  - `ds005270_pilot_final_approval_a1/docs/handoff/` 의 두 파일
  - `ds005270_qc_adoption/repo_additions/docs/handoff/` 의 한 파일
  - 정본은 저장소 `docs/handoff/` 쪽이다.
- 이 사본은 기록 보존용이다. 정본 판단은 `docs/handoff/` 와 checkpoint 를 따른다.

## sha256 (복사 직후, 원본 = 사본)

```
fd67732003a6913f9e37198cb99d03341c315d184833a907e58ff6e6a7f4db42  MoBSE_temporal_redesign_proposal_2026-10-17.md
302dd18c941da53cdd3c31616d6f78f5d4e135ce2ea45dce9f2761af9d5074bc  ds005270_approved_nuisance_v3/adoption_report.md
8052977f79b8522a6c4b076f08bbaa9ef0d8f7fbb449aed3a82b3055153cbc01  ds005270_audit_2026-10-17/PROTOCOL.md
f365a1dad997d0a968202bc17fe4579b323c18531098183283f4f09351477a81  ds005270_copy151_a1/delivery_report.md
82ddb8d8c60eec3939c15f46fd4c843c582dacae840e7a8e53ee8c8d5ab3fae8  ds005270_copy151_a1/plan_on_hold.md
892b2dee13b6093a8f726ae59709ff6aff26d7f2288d07ca0a4112053b0c4075  ds005270_copy151_a1/scripts_README.md
6c5ab92ac41fef5bbea0c5e77ecb1c54f0c3b63b156c88c5f43993664e60ac4c  ds005270_legacy_nuisance_validation_a1/review.md
6ecf2dae86f79e9866a2a061fb443ee38f2779b5f110c42c4c3b2a73f3e33455  ds005270_pilot_final_approval_a1/docs/handoff/ds005270_qc_v3_approved_2026-10-19.md
e16572c640ec5d9272020bd3bf1fd46865819df1a22b742b03a44b9aaba02309  ds005270_pilot_final_approval_a1/docs/handoff/ds005270_qc_v3_pilot_final_inclusion_2026-10-19.md
67e001955042b163a276c5f9f943dcd19dd454dfac9dddae8c174c13ccd7f779  ds005270_qc_adoption/repo_additions/docs/handoff/ds005270_qc_adoption_v2_2026-10-19.md
24548557f7b69810fd8879edce0c5dd428019672c5249bead643cfa44d25b978  ds005270_roi_adapter_validation_a1/review.md
62959a2d79ba87eb3f57ee8f71d6aaa0b8e722d795d3675809ecf3aaa6d4c02b  ds005270_targeted_visual_review_a1/review_report.md
```
