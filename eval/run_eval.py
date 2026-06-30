#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dev-only accuracy tool: compares saved Qwen output (eval/predictions/<id>.json)
against hand-corrected ground truth (eval/ground_truth/<id>.json).

Usage:
  python eval/run_eval.py

Workflow:
  1. Generate a contract via the app and save the returned `contract_data`
     into eval/predictions/<quotation_id>.json
  2. Copy that file into eval/ground_truth/<quotation_id>.json and hand-edit
     any field that the AI got wrong so it matches the real source document
  3. Run this script to see per-field and overall accuracy
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

EVAL_DIR = Path(__file__).resolve().parent
PREDICTIONS_DIR = EVAL_DIR / "predictions"
GROUND_TRUTH_DIR = EVAL_DIR / "ground_truth"


def normalize(value):
    if value is None:
        return ""
    return str(value).strip()


def values_match(expected, actual):
    e, a = normalize(expected), normalize(actual)
    if e == a:
        return True
    try:
        return abs(float(e.replace(",", "")) - float(a.replace(",", ""))) < 0.01
    except ValueError:
        return False


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    gt_files = sorted(GROUND_TRUTH_DIR.glob("*.json"))
    if not gt_files:
        print(f"ไม่พบไฟล์ ground truth ใน {GROUND_TRUTH_DIR}")
        return

    per_field_totals = defaultdict(lambda: [0, 0])  # field -> [matched, total]
    overall_matched, overall_total = 0, 0

    for gt_file in gt_files:
        quotation_id = gt_file.stem
        pred_file = PREDICTIONS_DIR / f"{quotation_id}.json"
        if not pred_file.exists():
            print(f"[ข้าม] ไม่พบ prediction สำหรับ {quotation_id} ({pred_file})")
            continue

        ground_truth = load_json(gt_file)
        predicted = load_json(pred_file)

        print(f"\n=== {quotation_id} ===")
        mismatches = 0
        for field, expected in ground_truth.items():
            actual = predicted.get(field)
            matched = field in predicted and values_match(expected, actual)

            counts = per_field_totals[field]
            counts[0] += int(matched)
            counts[1] += 1
            overall_total += 1
            overall_matched += int(matched)

            if not matched:
                mismatches += 1
                print(f"  ✗ {field}: expected={expected!r} actual={actual!r}")

        extra_fields = [k for k in predicted if k not in ground_truth]
        if extra_fields:
            print(f"  (ฟิลด์ที่ AI ส่งมาแต่ไม่มีใน ground truth: {extra_fields})")

        if mismatches == 0:
            print("  ✓ ตรงทุกฟิลด์")

    if overall_total == 0:
        print("ไม่มีคู่ prediction/ground truth ให้ประเมินผล")
        return

    print("\n=== สรุปความแม่นยำต่อฟิลด์ ===")
    for field, (matched, total) in sorted(per_field_totals.items()):
        if matched < total:
            print(f"  {field}: {matched}/{total} ({matched / total * 100:.1f}%)")

    print(f"\n=== ความแม่นยำโดยรวม: {overall_matched}/{overall_total} ({overall_matched / overall_total * 100:.1f}%) ===")


if __name__ == "__main__":
    main()
