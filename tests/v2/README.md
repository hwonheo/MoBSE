# tests/v2 — 재설계 v2 전용 검사

기존 `tests/` 에는 `mobse.data.hcp` 부재로 collection 단계에서 깨지는 파일이 있다
(`test_hcp_templates.py`, `test_subject_split.py`). `pyproject.toml` 의
`testpaths = ["tests"]` 때문에 인자 없이 `pytest` 를 돌리면 그것들까지 수집되어
**신규 gate evidence 가 legacy 실패로 오염된다**(차단 항목 U23).

따라서 v2 검사는 경로를 명시해 돌린다:

```bash
PYTHONPATH=. pytest tests/v2 -q
```

인자를 주면 `testpaths` 가 무시되므로 legacy 는 수집되지 않는다. 지침서 §4 가 요구하는
"기존 suite failure 와 신규 failure 를 별도 표로" 기록하는 전제가 이것이다.

| 파일 | 대응 acceptance test |
|---|---|
| `test_splits.py` | T03 subject isolation, T14 통계 단위(분할 쪽) |
| `test_statistics.py` | T13 endpoint 손계산, T14 bootstrap index |
