"""MoBSE 재설계 v2 모듈.

무거운 의존성을 여기서 import 하지 않는다. 기존 `mobse/data/__init__.py` 가
`etth1` 경유로 torch 를 강제 import 해 numpy 만 필요한 모듈까지 torch 없이는
쓸 수 없게 만든 문제(차단 항목 U24)를 되풀이하지 않기 위함이다.

각 모듈은 필요한 곳에서 직접 import 한다:
    from mobse.v2.splits import build_folds
    from mobse.v2.statistics import paired_bootstrap
"""

__all__ = ["splits", "statistics"]
