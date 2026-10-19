# ds005270 입력 준비·안전 커밋·코드 동기화 완료

전처리·QC 계산·학습은 시작하지 않았으며 실행 보류 상태다. 자동 실행·예약·보충 작업도 만들지 않았다. 원본과 기존6명 결과를 보존했다.

입력 복사 완료: 2026-10-18T23:43:19.654249+00:00. 남은 후보151명, 760파일, 8,896,432,701 bytes (약8.90GB). 서버 SHA-256 대조760/760 일치, 불일치0. T1w NIfTI/JSON와 n-back BOLD NIfTI/JSON/events, 필요한 BIDS metadata만 포함했다. 080·기존6명·다른task·다른데이터셋·분석산출물은 제외했다.

데이터 준비 경로: `/mnt/data/mp2026/MoBSE_dataset/ds005270_inputs_remaining151_20261019_a1/bids`. 전송명세·해시·실행보류계획은 같은 루트 `provenance/`에 있다. 기존 서버 입력6명과 저장소 원자료 부재를 확인한 뒤 새 경로에만 복사했다.

계획: 향후 QC 통과30명(기존4+추가26부터, 필요시 같은 고정순서 보충)을 목표로 삼되 지금은 계획뿐이다. 10% 문제를95%확률로1번 이상 발견하는 독립대상자 기준은29명이며, 성능 검정력 또는30eligible 보장은 아니다. seed20261019와 SHA256(seed|subject) 정렬로151명 순서를 고정했고 성능을 보지 않았다.

로컬 main 커밋(영문1줄,20–25단어,Conventional Commits,본문·co-author 없음):

- `6faf79c1d7afea7213f188eddaef9b445acc5d2f` — docs(ds005270): freeze the reproducible expansion candidate order and thirty participant feasibility plan while keeping preprocessing and training on hold during input staging
- `59818bf4739679b2558dd5f52aa6b4f9fb383434` — feat(ds005270): adopt fMRIPrep nuisance validation and scoped pilot inclusion with documented signal limitations while preserving existing QC rules and adding regression tests
- `bd8a469e6bdd3d60ba2418c5edce78607329e352` — feat(ds005270): preserve the original preprocessing pilot implementation and protocol while documenting historical AFNI behavior separately from current fMRIPrep approval and execution

범위: ds005270 관련38파일. 역사적 AFNI 파일럿 코드·프로토콜, fMRIPrep v2/v3 정책·어댑터·시각QC 및 최종4명 포함 근거, 실패시 포함 방지 검사, 실행보류 확장계획·고정순서. push·amend·force·이력변경 없음.

검사: 최종상태 pytest13개 통과, Python AST/JSON 파싱·shell bash -n·git diff --check 통과,151명 seed순서/초기26명/실행보류플래그/커밋형식 대조 통과. 초기 TSV CRLF 검사 실패는 백업 후 LF만 정리했고151행 값·순서는 동일함을 확인했다. 민감키 signature 검사에서 일치 없음, 원본영상·대형생성물·환경·라이선스 파일은 선택하지 않았다. 변경 범위 밖 모델 전체시험과 서버 데이터 의존 시험은 미실행이다. 과학적 QC 계산은 재실행하지 않았다.

남긴 변경: R2T 관련315개, 공용 체크포인트1개는 범위 혼합/별도작업이라 보존. ds005270 역사적 lock·source hash·run lineage 9개는 실행출처 기록이어서 로컬에 보존하고 커밋에서 제외했다. 상세 목록은 `remaining_git_status.txt`.

코드 동기화: `h197:/mnt/data/code/MoBSE`. 기존 파일 상태/해시와 관련 cwd 프로세스를 확인했으며31개 대상은 모두 새 파일이라 충돌0. dry-run 후 --delete 없이 코드·설정·문서·테스트31개만 전송; SHA-256 및 파일모드31/31 일치. .git/data/results/artifacts/work/derivatives/비밀/환경/라이선스/bytecode는 전송하지 않았다. 코드 manifest는 서버 `.backup/ds005270_sync_20261019_6faf79c_manifest.json`에도 보존했고 manifest 자체 해시도 일치한다.

서버 Git HEAD는85b5bfc로 그대로다(.git 미동기화). 기존 수정 체크포인트와 미추적 i1보고서·piop2_diag는 보존했으며, 새 ds005270 파일은 서버 Git에서 미추적으로 보이는 것이 정상이다. 작은 QC 결과7개는 로컬커밋에만 있고 코드 rsync에는 포함하지 않았으므로 서버에서 결과의존 시험을 실행하지 않았다.

근거 파일:

- [copy_completed.json](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_copy151_a1/copy_completed.json>)
- [transfer_manifest.json](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_copy151_a1/transfer_manifest.json>)
- [remote_hash_verification.log](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_copy151_a1/remote_hash_verification.log>)
- [completion_remote_state.log](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_copy151_a1/completion_remote_state.log>)
- [code_sync_manifest.json](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_copy151_a1/code_sync_manifest.json>)
- [final_checks.json](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_copy151_a1/final_checks.json>)
- [commit_selection.json](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_copy151_a1/commit_selection.json>)
- [remaining_git_status.txt](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_copy151_a1/remaining_git_status.txt>)
- [plan_on_hold.md](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_copy151_a1/plan_on_hold.md>)
