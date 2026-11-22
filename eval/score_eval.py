"""Scores the latest complete eval run for each model; writes a summary and a review file.
Usage (from the library-mcp folder):  uv run python eval/score_eval.py
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
RESULTS = HERE / "results"
CASES = json.loads((HERE / "cases.json").read_text())["cases"]
MODELS = ["haiku", "sonnet", "opus"]
# USD per million tokens (input, output). Taken from third-party price trackers;
# verify against Anthropic's pricing page before quoting.
PRICES = {"haiku": (0.10, 0.50), "sonnet": (2.00, 10.00), "opus": (4.00, 20.00)}
CHECKS = ["completed", "tools", "args", "answer", "db"]
LABELS = {
    "completed": "Finished without error",
    "tools": "Tool selection",
    "args": "Argument correctness",
    "answer": "Answer contains key facts",
    "db": "Write safety (database state)",
}


def load_latest(name):
    for path in sorted(RESULTS.glob(f"*_{name}.json"), reverse=True):
        records = json.loads(path.read_text())
        if len(records) == len(CASES):  # skip partial smoke runs
            return {r["case"]: r for r in records}
    return None


def arg_ok(check, calls):
    for call in calls:
        if call["name"] != check["tool"]:
            continue
        value = call["input"].get(check["arg"])
        if check["op"] == "absent_or_null" and value in (None, ""):
            return True
        if value is None:
            continue
        text, want = str(value), str(check.get("value", ""))
        if check["op"] == "equals" and text == want:
            return True
        if check["op"] == "equals_ci" and text.lower() == want.lower():
            return True
        if check["op"] == "contains_ci" and want.lower() in text.lower():
            return True
    return False


def score(case, rec):
    calls = rec["tool_calls"]
    used = {c["name"] for c in calls}
    result = {"completed": rec["error"] is None}
    if "expected_tools" in case or "forbidden_tools" in case:
        result["tools"] = (
            all(t in used for t in case.get("expected_tools", []))
            and not any(t in used for t in case.get("forbidden_tools", []))
        )
    if "arg_checks" in case:
        result["args"] = all(arg_ok(c, calls) for c in case["arg_checks"])
    if "answer_includes" in case:
        text = rec["final_text"]
        result["answer"] = all(
            re.search(r"\b" + re.escape(t) + r"\b", text, re.I) for t in case["answer_includes"]
        )
    if "db_expect" in case:
        if case["db_expect"] == "inserted":
            result["db"] = rec["inserted"] == case.get("inserted_urls", [])
        else:
            result["db"] = rec["inserted"] == []
    return result


def cost(name, rec):
    p_in, p_out = PRICES[name]
    return (rec["input_tokens"] * p_in + rec["output_tokens"] * p_out) / 1_000_000


def main():
    data = {m: load_latest(m) for m in MODELS}
    missing = [m for m, d in data.items() if d is None]
    if missing:
        raise SystemExit(f"No complete run found for: {', '.join(missing)}")
    scores = {m: {c["id"]: score(c, data[m][c["id"]]) for c in CASES} for m in MODELS}

    rows = ["| Measure | " + " | ".join(MODELS) + " |", "|---|" + "---|" * len(MODELS)]
    for key in CHECKS:
        cells = []
        for m in MODELS:
            vals = [s[key] for s in scores[m].values() if key in s]
            cells.append(f"{sum(vals)}/{len(vals)}" if vals else "n/a")
        rows.append(f"| {LABELS[key]} | " + " | ".join(cells) + " |")
    rows.append("| Cases passing every automatic check | " + " | ".join(
        f"{sum(all(s.values()) for s in scores[m].values())}/{len(CASES)}" for m in MODELS) + " |")

    def per_model(fn):
        return [fn(m, [data[m][c["id"]] for c in CASES]) for m in MODELS]

    rows.append("| Average tool calls per case | " + " | ".join(per_model(
        lambda m, recs: f"{sum(len(r['tool_calls']) for r in recs) / len(recs):.1f}")) + " |")
    rows.append("| Average seconds per case | " + " | ".join(per_model(
        lambda m, recs: f"{sum(r['elapsed_s'] for r in recs) / len(recs):.1f}")) + " |")
    rows.append("| Slowest case (seconds) | " + " | ".join(per_model(
        lambda m, recs: f"{max(r['elapsed_s'] for r in recs):.1f}")) + " |")
    rows.append("| Total tokens in / out | " + " | ".join(per_model(
        lambda m, recs: f"{sum(r['input_tokens'] for r in recs):,} / {sum(r['output_tokens'] for r in recs):,}")) + " |")
    rows.append("| Cost for all 12 cases (USD) | " + " | ".join(per_model(
        lambda m, recs: f"${sum(cost(m, r) for r in recs):.3f}")) + " |")
    rows.append("| Cost per case (USD) | " + " | ".join(per_model(
        lambda m, recs: f"${sum(cost(m, r) for r in recs) / len(recs):.4f}")) + " |")

    failures = []
    for m in MODELS:
        for case_id, s in scores[m].items():
            bad = [LABELS[k] for k, v in s.items() if not v]
            if bad:
                failures.append(f"- {m} {case_id}: failed {', '.join(bad)}")

    summary = "\n".join(rows)
    summary += "\n\nAutomatic failures:\n" + ("\n".join(failures) if failures else "- none")
    summary += "\n\nCases marked manual_review also need a human read; see review.md."
    (RESULTS / "summary.md").write_text(summary + "\n")
    print(summary)

    out = ["# Eval review: every case, every model\n"]
    for case in CASES:
        out.append(f"## {case['id']} ({case['category']}): {case['prompt']}\n")
        if "manual_review" in case:
            out.append(f"**Review criterion:** {case['manual_review']}\n")
        for m in MODELS:
            rec = data[m][case["id"]]
            out.append(f"### {m}  (auto: {scores[m][case['id']]})")
            calls = [
                f"{c['name']}({json.dumps(c['input'])})" + (" -> ERROR" if c["is_error"] else "")
                for c in rec["tool_calls"]
            ]
            out.append("Tool calls: " + (" ; ".join(calls) if calls else "(none)"))
            out.append("Saved links: " + (", ".join(rec["inserted"]) or "(none)"))
            out.append("Answer:\n" + rec["final_text"].strip() + "\n")
    (RESULTS / "review.md").write_text("\n".join(out))
    print("\nWrote eval/results/summary.md and eval/results/review.md")


main()