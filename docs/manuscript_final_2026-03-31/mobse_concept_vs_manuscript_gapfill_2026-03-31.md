# MoBSE Concept vs Manuscript Gap Fill (2026-03-31)

목적: `docs/concept/MoBSE_note.md`와 현재 manuscript 최종 묶음을 대조해, 이론적 근거와 실험 증명의 부족분을 제출 전 체크리스트로 고정한다.

## 1) Concept-to-Manuscript Mapping

| Concept note claim | Manuscript evidence now | Gap level |
|---|---|---|
| Connectivity template는 인과 모델이 아니라 통계적 routing prior | Intro/Methods/Discussion에 경계 문장 반영 | low |
| Yeo-7은 공통 해석 좌표(scaffold) | Intro/Discussion에서 주축으로 반영 | low |
| Sparse specialization은 효율-성능 균형을 만든다 | matched FLOPs 성능 비교, rerun10 재현 확인 | medium |
| Routing이 해석 가능성을 만든다 | entropy/stability 지표 보고 | medium |
| 재현성은 다중 seed로 확인해야 한다 | rerun10 완료 (`42..51`) | low |
| 전처리/하모나이제이션 민감도는 핵심 위험 | 위험은 서술됨, 직접 실험선은 부족 | high |
| split leakage 위험 통제 필요 | window split 한계 명시됨, strict split 미완 | high |

## 2) What Is Proven vs Not Yet Proven

### Proven enough for main text
- 동일 연산 제약에서 주된 성능 차이(OS) 확인
- 10-seed 재실행으로 결과 재현성 확보
- ETT-family 10-seed 보조 확장으로 과제 난이도 분화 확인

### Not yet proven strongly
- subject-level strict split에서 OS 결론 유지 여부
- denoising/harmonization 설정 변화에서 효과 크기 안정성
- latency/memory 효율의 고정 harness 재현성

## 3) Submission-hardening Priority

1. strict split rerun (OS 중심)  
2. preprocessing sensitivity matrix (최소 2-3 preset)  
3. site/partition robustness (가능한 범위 내)  
4. fixed harness로 latency/memory 반복 측정

## 4) Writing Policy

- 메인 claim은 `H2/H3` 중심으로 작성한다(동일 연산 제약 + rerun10 재현).
- `H1`(라우팅 해석)은 "부분 지지"로 표현하고 과장하지 않는다.
- `H4/H5`(strict split, preprocessing robustness)는 제한점과 계획이 아니라 "제출 전 보강 실험"으로 명시한다.
