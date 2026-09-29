"""MoBSE exploratory v2 (코드 모듈 이름은 ``v3``) — 결정 27·30·31·32.

v1 (재설계 v1) 의 ``mobse/v2`` 는 **동결**이다. v1 release 의 측정 잠금
``9b7b11cf`` · 구현 잠금 ``bcf1fec22676`` 와 gate revision 75 가 그 파일들을
해시하고 있으므로, 이 모듈은 v2 를 **읽기만** 한다.

이 모듈이 바꾸는 것 (결정 28·30·31·32):

* 학습 규칙 — update 예산 고정, epoch 상한 없음, best checkpoint 선택 자유 (``train``)
* ROI 정체 구조 두 가지 — ROI embedding · ROI 별 readout (``models``, 예정)
* null 세 종류 — 순열 · Váša 회전 (spin) · degree 보존 rewiring (``templates``, 예정)
* 학습 subject 부분표집 — 저표본 곡선 (예정)

**구현 선택 (표시)**: 크게 바뀌는 모듈만 이 패키지에 새로 쓰고, 바뀌지 않는 것
(manifests · preprocess · splits · features · extract · labels · locks · cohort ·
evaluate · statistics · baselines) 은 ``mobse.v2`` 를 import 해 쓴다. v3 잠금의
``code_hash`` 는 ``mobse/v3/*.py`` 와 ``mobse/v2/*.py`` 를 **함께** 해시한다.
"""

VERSION = "exploratory_v2"
