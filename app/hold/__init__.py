"""成品扣货排查域。

可疑来料进入工序后，依据报工批次血缘与交接对账结果，圈定发货前必须扣住的成品。
"""

from app.hold.engine import evaluate
from app.hold.normalize import normalize_investigation
from app.hold.reasons import DECISION_HELD, DECISION_RELEASED, HOLD_REASONS, RELEASE_REASONS

__all__ = [
    "evaluate",
    "normalize_investigation",
    "HOLD_REASONS",
    "RELEASE_REASONS",
    "DECISION_HELD",
    "DECISION_RELEASED",
]
