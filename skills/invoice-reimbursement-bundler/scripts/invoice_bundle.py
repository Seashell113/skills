#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发票报销打包脚本。

提供三个命令：
- scan：扫描目录，输出发票明细、总额、重复发票号、无法解析文件列表。
- bundle：计算满足目标金额的最优发票组合，默认只输出不改动文件。
- bundle --apply：将选中发票复制或移动到结果目录，并校验结果。

设计约束：
- 只读取 PDF 文本，不依赖 OCR；扫描件若无法提取文本会被标记为无法解析。
- 金额计算使用 Decimal；发票唯一性以发票号为准。
- 支持中文路径和文件名。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable, NamedTuple

import pdfplumber


class Invoice(NamedTuple):
    invoice_no: str
    amount: Decimal
    path: Path
    source_dir: Path


class ParseResult(NamedTuple):
    invoice_no: str | None
    amount: Decimal | None


# ---------------------------------------------------------------------------
# 文本解析
# ---------------------------------------------------------------------------

_INVOICE_NO_PATTERNS = [
    re.compile(r"发票号码\s*[：:]\s*(\d{10,20})"),
    re.compile(r"发票号码\s*(\d{10,20})"),
]

_AMOUNT_PATTERNS = [
    # 价税合计（小写）常见写法
    re.compile(r"价税合计\s*(?:[^\n\r]{0,40}?)\s*[¥￥]\s*([\d,]+\.?\d{0,2})"),
    re.compile(r"价税合计\s*[¥￥]?\s*([\d,]+\.?\d{0,2})"),
    # 作为兜底，查找 "合计" 后的金额，但尽量避开纯数字行号
    re.compile(r"合\s*计\s*(?:[^\n\r]{0,30}?)\s*[¥￥]\s*([\d,]+\.?\d{0,2})"),
]


def _extract_text_from_pdf(path: Path) -> str:
    """从 PDF 提取全部页面文本。"""
    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n".join(parts)


def _normalize_amount(raw: str) -> Decimal | None:
    """将字符串金额转为 Decimal，失败返回 None。"""
    cleaned = raw.replace(",", "").replace(" ", "").strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def parse_invoice(path: Path) -> ParseResult:
    """解析单张 PDF 发票，返回（发票号，金额）。解析失败字段为 None。"""
    try:
        text = _extract_text_from_pdf(path)
    except Exception:
        return ParseResult(None, None)

    if not text or not text.strip():
        return ParseResult(None, None)

    invoice_no: str | None = None
    for pat in _INVOICE_NO_PATTERNS:
        m = pat.search(text)
        if m:
            invoice_no = m.group(1)
            break

    amount: Decimal | None = None
    for pat in _AMOUNT_PATTERNS:
        m = pat.search(text)
        if m:
            amount = _normalize_amount(m.group(1))
            if amount is not None:
                break

    return ParseResult(invoice_no, amount)


def _is_pdf(path: Path) -> bool:
    return path.suffix.lower() == ".pdf"


def scan_directories(dirs: Iterable[Path]) -> tuple[list[Invoice], list[Path]]:
    """扫描多个目录，返回（成功解析发票，无法解析文件）。"""
    invoices: list[Invoice] = []
    unparsable: list[Path] = []

    for d in dirs:
        if not d.exists():
            continue
        for path in sorted(d.rglob("*")):
            if not path.is_file() or not _is_pdf(path):
                continue
            parsed = parse_invoice(path)
            if parsed.invoice_no is None or parsed.amount is None:
                unparsable.append(path)
                continue
            invoices.append(
                Invoice(
                    invoice_no=parsed.invoice_no,
                    amount=parsed.amount,
                    path=path,
                    source_dir=d,
                )
            )

    return invoices, unparsable


# ---------------------------------------------------------------------------
# 组合求解
# ---------------------------------------------------------------------------


def _solve_subset(
    invoices: list[Invoice], target: Decimal
) -> tuple[list[Invoice], list[Invoice], Decimal] | None:
    """找出发票子集，使总额 >= target 且超出最小；超出相同时张数最少。

    返回 (selected, unselected, total)；若无解返回 None。
    """
    if target <= 0:
        return [], invoices, Decimal("0.00")

    target_cents = int((target * 100).to_integral_value(rounding=ROUND_HALF_UP))
    n = len(invoices)
    if n == 0:
        return None

    # 金额按大到小排序，配合分支限界快速收敛。
    indexed = sorted(
        enumerate(invoices), key=lambda x: x[1].amount, reverse=True
    )
    amounts_cents = [int((inv.amount * 100).to_integral_value(rounding=ROUND_HALF_UP)) for _, inv in indexed]
    total_cents = sum(amounts_cents)
    if total_cents < target_cents:
        return None

    best_sum: int | None = None
    best_mask: int = 0
    best_count: int = n + 1

    # 前缀和，用于剪枝。
    prefix_sums = [0] * (n + 1)
    for i in range(n - 1, -1, -1):
        prefix_sums[i] = prefix_sums[i + 1] + amounts_cents[i]

    def dfs(idx: int, current_sum: int, current_count: int, mask: int) -> None:
        nonlocal best_sum, best_mask, best_count

        if current_sum >= target_cents:
            # 更新最优解
            improve = False
            if best_sum is None:
                improve = True
            elif current_sum < best_sum:
                improve = True
            elif current_sum == best_sum and current_count < best_count:
                improve = True
            if improve:
                best_sum = current_sum
                best_mask = mask
                best_count = current_count
            # 即使已经达标，继续往后也可能找到更小超出的解；但当前和已 >= target，
            # 只有加入更多才可能改变（只会变大），因此这里可以剪枝。
            return

        if idx >= n:
            return

        # 剪枝 1：即使把剩余全加上也达不到 target，且当前未达标。
        if current_sum + prefix_sums[idx] < target_cents:
            return

        # 剪枝 2：当前和加上所有剩余项都 >= best_sum 时，不可能更优。
        if best_sum is not None and current_sum + prefix_sums[idx] >= best_sum:
            # 若当前和 + 剩余最大可能和 >= best_sum，则存在更大超出的可能，
            # 只剪掉严格不可能小于 best_sum 的分支。
            if current_sum + prefix_sums[idx] < best_sum:
                return

        # 选当前项
        dfs(
            idx + 1,
            current_sum + amounts_cents[idx],
            current_count + 1,
            mask | (1 << idx),
        )
        # 不选当前项
        dfs(idx + 1, current_sum, current_count, mask)

    dfs(0, 0, 0, 0)

    if best_sum is None:
        return None

    selected_idx = [original_idx for i, (original_idx, _) in enumerate(indexed) if best_mask & (1 << i)]
    selected = [invoices[i] for i in selected_idx]
    selected_set = set(selected_idx)
    unselected = [invoices[i] for i in range(n) if i not in selected_set]
    total = Decimal(best_sum) / 100
    return selected, unselected, total


# ---------------------------------------------------------------------------
# 命令实现
# ---------------------------------------------------------------------------


def _path_list(raw: str) -> list[Path]:
    return [Path(p).expanduser().resolve() for p in raw.split(",") if p.strip()]


def cmd_scan(args: argparse.Namespace) -> int:
    inputs = _path_list(args.inputs)
    invoices, unparsable = scan_directories(inputs)

    duplicates: dict[str, list[Path]] = defaultdict(list)
    for inv in invoices:
        duplicates[inv.invoice_no].append(inv.path)
    duplicate_nos = {no: paths for no, paths in duplicates.items() if len(paths) > 1}

    total = sum((inv.amount for inv in invoices), Decimal("0.00"))

    result = {
        "inputs": [str(p) for p in inputs],
        "invoice_count": len(invoices),
        "total": f"{total:.2f}",
        "duplicates": {
            no: [str(p) for p in paths] for no, paths in sorted(duplicate_nos.items())
        },
        "unparsable": [str(p) for p in unparsable],
        "invoices": [
            {
                "invoice_no": inv.invoice_no,
                "amount": f"{inv.amount:.2f}",
                "path": str(inv.path),
            }
            for inv in sorted(invoices, key=lambda x: (x.source_dir, x.path.name))
        ],
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_bundle(args: argparse.Namespace) -> int:
    inputs = _path_list(args.inputs)
    target = Decimal(args.target).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    invoices, unparsable = scan_directories(inputs)

    # 去重：同一发票号出现多次时，只保留第一个；其余计入 unselected 但不参与组合。
    seen_nos: set[str] = set()
    unique_invoices: list[Invoice] = []
    duplicate_files: list[Path] = []
    for inv in invoices:
        if inv.invoice_no in seen_nos:
            duplicate_files.append(inv.path)
        else:
            seen_nos.add(inv.invoice_no)
            unique_invoices.append(inv)

    solution = _solve_subset(unique_invoices, target)

    result: dict = {
        "inputs": [str(p) for p in inputs],
        "target": f"{target:.2f}",
        "invoice_count": len(invoices),
        "unique_count": len(unique_invoices),
        "duplicate_files": [str(p) for p in duplicate_files],
        "unparsable": [str(p) for p in unparsable],
        "solved": solution is not None,
    }

    if solution is None:
        available = sum((inv.amount for inv in unique_invoices), Decimal("0.00"))
        result["available_total"] = f"{available:.2f}"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    selected, unselected, total = solution
    excess = total - target

    result.update(
        {
            "selected": [
                {
                    "invoice_no": inv.invoice_no,
                    "amount": f"{inv.amount:.2f}",
                    "path": str(inv.path),
                }
                for inv in selected
            ],
            "unselected": [
                {
                    "invoice_no": inv.invoice_no,
                    "amount": f"{inv.amount:.2f}",
                    "path": str(inv.path),
                }
                for inv in unselected
            ],
            "selected_count": len(selected),
            "selected_total": f"{total:.2f}",
            "excess": f"{excess:.2f}",
        }
    )

    if args.apply:
        output_root = Path(args.output_root).expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        result_dir = output_root / f"报销{int(target)}_{total:.2f}"
        if result_dir.exists():
            # 若已存在，追加计数避免覆盖。
            counter = 1
            base_name = f"报销{int(target)}_{total:.2f}"
            while result_dir.exists():
                result_dir = output_root / f"{base_name}_{counter}"
                counter += 1
        result_dir.mkdir(parents=True, exist_ok=False)

        mode = args.mode
        if mode not in ("copy", "move"):
            print(json.dumps({"error": f"--mode must be copy or move, got {mode}"}, ensure_ascii=False, indent=2))
            return 2

        copied: list[Path] = []
        for inv in selected:
            dest = result_dir / inv.path.name
            # 处理同名文件：保留源目录名作为前缀。
            if dest.exists():
                safe_name = f"{inv.source_dir.name}_{inv.path.name}"
                dest = result_dir / safe_name
            if mode == "copy":
                shutil.copy2(inv.path, dest)
            else:
                shutil.move(str(inv.path), str(dest))
            copied.append(dest)

        # 执行后再次扫描结果目录并校验合计金额。
        result_invoices, result_unparsable = scan_directories([result_dir])
        result_total = sum((inv.amount for inv in result_invoices), Decimal("0.00"))

        result["result_dir"] = str(result_dir)
        result["mode"] = mode
        result["result_invoice_count"] = len(result_invoices)
        result["result_total"] = f"{result_total:.2f}"
        result["result_unparsable"] = [str(p) for p in result_unparsable]

        if result_total != total:
            result["verify_ok"] = False
            result["verify_error"] = (
                f"结果目录合计 {result_total:.2f} 与预期 {total:.2f} 不一致"
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 3

        result["verify_ok"] = True

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="发票报销打包：扫描、组合、复制/移动。"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="扫描目录并输出明细")
    scan_parser.add_argument(
        "--inputs",
        required=True,
        help="输入目录，多个用逗号分隔（支持中文路径）",
    )

    bundle_parser = subparsers.add_parser("bundle", help="计算最优组合或执行打包")
    bundle_parser.add_argument(
        "--target",
        required=True,
        help="目标金额，例如 3000",
    )
    bundle_parser.add_argument(
        "--inputs",
        required=True,
        help="输入目录，多个用逗号分隔（支持中文路径）",
    )
    bundle_parser.add_argument(
        "--output-root",
        default=".",
        help="结果目录根路径，默认当前目录",
    )
    bundle_parser.add_argument(
        "--apply",
        action="store_true",
        help="实际复制或移动文件；否则仅输出组合方案",
    )
    bundle_parser.add_argument(
        "--mode",
        default="copy",
        choices=["copy", "move"],
        help="apply 时的操作方式，默认 copy",
    )

    args = parser.parse_args(argv)

    if args.command == "scan":
        return cmd_scan(args)
    if args.command == "bundle":
        return cmd_bundle(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
