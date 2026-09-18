"""序列修复预演（不落库）。

针对一次已有审计中的 serial 序列，给出一个逐项严格单调前进的修复
预演结果：首个 serial 保持不变；其后每项都与上一个**修复后值**按
RFC 1982 比较，有效前进则保留原值，否则替换为上一个修复后值加 1
（按 32 位无符号整数回绕）。

预演结果仅用于展示，不写入数据库。
"""
from __future__ import annotations

from .rfc1982 import (
    REL_ADVANCE,
    REL_EQUAL,
    REL_INCOMPARABLE,
    REL_REGRESSION,
    SERIAL_SPACE,
    classify,
)

KEEP = "keep"
REPLACE = "replace"

_REPLACE_REASONS = {
    REL_EQUAL: "与上一个修复后值相等，不构成有效前进，替换为上一个修复后值加 1",
    REL_REGRESSION: "相对上一个修复后值发生倒退，从服务器会拒绝更新，替换为上一个修复后值加 1",
    REL_INCOMPARABLE: "与上一个修复后值相距恰好 2^31，RFC 1982 下不可比较，替换为上一个修复后值加 1",
}


def build_repair_plan(serials: list[int]) -> tuple[list[dict], dict]:
    """对 serial 序列做修复预演，返回 (items, summary)。

    每个 item 包含：index、original、effective、action、reason；
    summary 汇总 total、kept、replaced 数量。
    """
    items: list[dict] = []
    replaced_count = 0
    prev_effective: int | None = None

    for index, serial in enumerate(serials):
        if index == 0:
            # 首个 serial 保持不变
            action = KEEP
            effective = serial
            reason = "首个观测值保持不变，作为修复序列的基准"
        else:
            relation = classify(prev_effective, serial)
            if relation == REL_ADVANCE:
                action = KEEP
                effective = serial
                reason = "相对上一个修复后值为 RFC 1982 意义下的有效前进，保留原值"
            else:
                action = REPLACE
                effective = (prev_effective + 1) % SERIAL_SPACE
                reason = _REPLACE_REASONS[relation]
                replaced_count += 1

        items.append(
            {
                "index": index,
                "original": serial,
                "effective": effective,
                "action": action,
                "reason": reason,
            }
        )
        prev_effective = effective

    summary = {
        "total": len(serials),
        "kept": len(serials) - replaced_count,
        "replaced": replaced_count,
    }
    return items, summary
