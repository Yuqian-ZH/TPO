#!/usr/bin/env python3
"""Task 1 output diagnostics: format residue, truncation, per-prompt win/loss/tie, judge usage.

CPU only, standard library only. Reads files already produced on the server:
  stages/<stage>.json             AlpacaEval-format outputs (instruction, output, ...)
  eval_out/<stage>/annotations.json  weighted judge annotations (preference in [1, 2])
  eval_out/<stage>/leaderboard.csv   used only to sanity-check recomputed WR
  eval_out/<stage>/usage.jsonl       per-request token usage

Usage:
  python3 diagnose_outputs.py                     # root = this script's folder
  python3 diagnose_outputs.py --root path/to/task1 --tokenizer allenai/Llama-3.1-Tulu-3-8B-SFT
Writes <root>/diagnostics/{report.md, worst_cases.md, per_prompt.csv, flags.json}.
"""
import argparse
import csv
import json
import re
import statistics
import sys
from pathlib import Path

STAGES = ["baseline", "step0", "step1", "step2", "bon15"]
PAIRS = [("step1", "baseline"), ("step2", "step1"), ("step2", "step0"), ("step2", "bon15")]
WORST_PAIRS = [("step2", "step0"), ("step2", "bon15")]

TAG_RE = re.compile(
    r"</?\s*(IMPROVED_VARIABLE|VARIABLE|FEEDBACK|LM_INPUT|LM_OUTPUT|LM_SYSTEM_PROMPT|CONTEXT|"
    r"ROLE|OBJECTIVE_FUNCTION|PREDICTION|CONVERSATION|START_OF_[A-Z_]+|END_OF_[A-Z_]+)\s*>",
    re.I,
)
GENERIC_TAG_RE = re.compile(r"</?[A-Z][A-Z_]{3,}>")
META_RES = {
    "improved/revised X": re.compile(r"\b(improved|revised|refined|updated) (response|version|answer|variable)\b", re.I),
    "chosen/rejected response": re.compile(r"\b(chosen|rejected) response\b", re.I),
    "here is the improved": re.compile(r"\bhere(?: is|'s) (?:the|an|my) (?:improved|revised|updated|refined)\b", re.I),
    "refers to feedback": re.compile(r"\b(?:based on|incorporating|addressing|address(?:es)?) the (?:feedback|critique|gradient)\b", re.I),
    "textual gradient": re.compile(r"\btextual gradient\b", re.I),
    "the previous response": re.compile(r"\bthe (?:above|previous|original|initial) response\b", re.I),
}
TERMINAL = set(".!?\u3002\uff01\uff1f)]}\"'\u201d\u2019`*|>~")
TEXT_KEYS = ("output", "response", "answer", "completion")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        lists = [v for v in data.values() if isinstance(v, list)]
        if len(lists) != 1:
            sys.exit(f"{path}: expected a list of records, got dict with keys {list(data)[:10]}")
        data = lists[0]
    return data


def text_of(rec):
    for k in TEXT_KEYS:
        if isinstance(rec.get(k), str):
            return rec[k]
    sys.exit(f"record has none of {TEXT_KEYS}: keys={list(rec)}")


def rm_of(rec):
    for k in ("rm", "rm_score", "reward", "score"):
        if isinstance(rec.get(k), (int, float)):
            return float(rec[k])
    return None


def find_stage_file(root, stage):
    exact = root / "stages" / f"{stage}.json"
    if exact.exists():
        return exact
    hits = [p for p in (root / "stages").glob(f"*{stage}*.json") if "summary" not in p.name]
    if len(hits) == 1:
        return hits[0]
    sys.exit(f"cannot locate stage file for {stage!r} under {root/'stages'} (candidates: {hits})")


def keyed(records, inst_key="instruction"):
    """Key records by (instruction, occurrence) so duplicate instructions stay distinct."""
    seen, out = {}, {}
    for r in records:
        inst = r[inst_key]
        n = seen.get(inst, 0)
        seen[inst] = n + 1
        out[(inst, n)] = r
    return out


def make_counter(tok_name):
    if not tok_name:
        return None
    try:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(tok_name)
        return lambda s: len(tok.encode(s, add_special_tokens=False))
    except Exception as e:  # tokenizer is optional; fall back to char heuristics
        print(f"[warn] tokenizer unavailable ({e}); using character heuristics", file=sys.stderr)
        return None


def flags_for(text, count_tokens, cap, char_cap):
    s = text.rstrip()
    tags = sorted({m.group(0) for m in TAG_RE.finditer(text)} | {m.group(0) for m in GENERIC_TAG_RE.finditer(text)})
    meta = {name: [m.group(0) for m in rx.finditer(text)] for name, rx in META_RES.items()}
    meta = {k: v for k, v in meta.items() if v}
    ntok = count_tokens(text) if count_tokens else None
    near_cap = (ntok >= cap - 16) if ntok is not None else (len(text) >= char_cap)
    return {
        "chars": len(text),
        "tokens": ntok,
        "tags": tags,
        "meta": meta,
        "empty": not s,
        "near_cap": near_cap,
        "no_terminal_punct": bool(s) and s[-1] not in TERMINAL and not s.endswith("```"),
        "unclosed_fence": text.count("```") % 2 == 1,
    }


def snippet(text, pattern, width=60):
    i = text.find(pattern)
    if i < 0:
        return ""
    a, b = max(0, i - width), min(len(text), i + len(pattern) + width)
    return ("…" if a else "") + text[a:b].replace("\n", " ⏎ ") + ("…" if b < len(text) else "")


def load_scores(root, stage, outputs):
    """Per-prompt model score in [0, 1] (= preference - 1, flipped if the model is output_1)."""
    path = root / "eval_out" / stage / "annotations.json"
    anns = keyed(load_json(path))
    scores, flipped, unmatched = {}, 0, 0
    for k, a in anns.items():
        pref = a.get("preference")
        if pref is None or pref != pref:
            continue
        out = outputs.get(k)
        model_text = text_of(out) if out else None
        if model_text is not None and a.get("output_1") == model_text and a.get("output_2") != model_text:
            scores[k] = 2.0 - float(pref)
            flipped += 1
        else:
            if model_text is not None and a.get("output_2") != model_text:
                unmatched += 1
            scores[k] = float(pref) - 1.0
    return scores, {"annotations": len(anns), "flipped": flipped, "unmatched_text": unmatched}


def leaderboard_wr(root, stage):
    path = root / "eval_out" / stage / "leaderboard.csv"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for k in ("win_rate", "winrate"):
            if row.get(k):
                return float(row[k])
    return None


def usage_stats(root, stage):
    path = root / "eval_out" / stage / "usage.jsonl"
    if not path.exists():
        return None
    comp, reason = [], []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "completion_tokens" and isinstance(v, (int, float)):
                    comp.append(v)
                elif k == "reasoning_tokens" and isinstance(v, (int, float)):
                    reason.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                walk(json.loads(line))
    if not comp:
        return {"requests_with_completion_tokens": 0}
    return {
        "requests_with_completion_tokens": len(comp),
        "mean_completion_tokens": statistics.mean(comp),
        "max_completion_tokens": max(comp),
        "reasoning_tokens_seen": len(reason),
        "max_reasoning_tokens": max(reason) if reason else None,
    }


def fenced(text):
    fence = "`" * max(3, max((len(m) for m in re.findall(r"`{3,}", text)), default=0) + 1)
    return f"{fence}text\n{text}\n{fence}"


def fmt(x, nd=3):
    return "—" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--tie", type=float, default=0.05, help="|Δ score| below this counts as a tie")
    ap.add_argument("--cap", type=int, default=2048, help="response token cap used in generation")
    ap.add_argument("--char-cap", type=int, default=7500, help="near-cap heuristic when no tokenizer")
    ap.add_argument("--worst", type=int, default=15)
    ap.add_argument("--tokenizer", default=None, help="optional HF tokenizer name/path (needs transformers)")
    args = ap.parse_args()
    root, out_dir = args.root.resolve(), (args.out or args.root / "diagnostics").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    count_tokens = make_counter(args.tokenizer)

    outputs = {s: keyed(load_json(find_stage_file(root, s))) for s in STAGES}
    keys = list(outputs["baseline"])
    for s in STAGES:
        if set(outputs[s]) != set(keys):
            sys.exit(f"stage {s} prompts differ from baseline ({len(outputs[s])} vs {len(keys)})")

    flags = {s: {k: flags_for(text_of(outputs[s][k]), count_tokens, args.cap, args.char_cap) for k in keys} for s in STAGES}
    scores, match_info = {}, {}
    for s in STAGES:
        scores[s], match_info[s] = load_scores(root, s, outputs[s])

    L = ["# Task 1 output diagnostics", ""]
    L += [f"Root: `{root}`; prompts: {len(keys)}; tie threshold |Δ| < {args.tie}; "
          f"token counts: {'tokenizer ' + args.tokenizer if count_tokens else f'not available (near-cap = ≥ {args.char_cap} chars)'}.", ""]

    L += ["## Sanity check: recomputed WR vs leaderboard", "",
          "| Stage | Annotations | Recomputed WR (%) | Leaderboard WR (%) | Output_1 = model (flipped) | Text mismatches |",
          "|---|---:|---:|---:|---:|---:|"]
    for s in STAGES:
        sc = list(scores[s].values())
        wr = 100 * statistics.mean(sc) if sc else None
        mi = match_info[s]
        L.append(f"| {s} | {mi['annotations']} | {fmt(wr, 2)} | {fmt(leaderboard_wr(root, s), 2)} | {mi['flipped']} | {mi['unmatched_text']} |")
    L += ["", "If recomputed and leaderboard WR disagree, per-prompt matching is wrong; do not trust the tables below.", ""]

    L += ["## Format residue and truncation (counts out of prompts)", "",
          "| Stage | TextGrad/caps tags | Meta phrases | Empty | Near cap | No terminal punct. | Unclosed ``` | Mean chars | Max chars | Max tokens |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for s in STAGES:
        f = flags[s].values()
        toks = [x["tokens"] for x in f if x["tokens"] is not None]
        L.append("| " + " | ".join([
            s,
            str(sum(bool(x["tags"]) for x in f)),
            str(sum(bool(x["meta"]) for x in f)),
            str(sum(x["empty"] for x in f)),
            str(sum(x["near_cap"] for x in f)),
            str(sum(x["no_terminal_punct"] for x in f)),
            str(sum(x["unclosed_fence"] for x in f)),
            f"{statistics.mean(x['chars'] for x in f):.0f}",
            str(max(x["chars"] for x in f)),
            str(max(toks)) if toks else "—",
        ]) + " |")
    L += ["", "baseline / step0 / bon15 never pass through TextGrad, so they are the control rate for every column.", ""]

    L += ["### Meta-phrase breakdown", "", "| Pattern | " + " | ".join(STAGES) + " |", "|---|" + "---:|" * len(STAGES)]
    for name in META_RES:
        L.append(f"| {name} | " + " | ".join(str(sum(name in flags[s][k]["meta"] for k in keys)) for s in STAGES) + " |")
    L.append("")

    L += ["### Residue examples (step1 / step2)", ""]
    shown = 0
    for s in ("step1", "step2"):
        for k in keys:
            fl, text = flags[s][k], text_of(outputs[s][k])
            hits = fl["tags"] + [v[0] for v in fl["meta"].values()]
            if hits and shown < 20:
                L.append(f"- **{s}** · `{k[0][:70]}` · {', '.join(sorted(set(hits)))[:120]}  \n  {snippet(text, hits[0])}")
                shown += 1
    if not shown:
        L.append("None found.")
    L.append("")

    L += ["## Per-prompt win / loss / tie", "",
          "Score = weighted preference against the same GPT-4 reference, in [0, 1]. Δ = A − B per prompt.", "",
          "| A vs B | Wins | Losses | Ties | Identical text | Mean Δ (pp) | Δ from the 10 worst prompts (pp) |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    rows = []
    for a, b in PAIRS:
        common = [k for k in keys if k in scores[a] and k in scores[b]]
        deltas = {k: scores[a][k] - scores[b][k] for k in common}
        ident = sum(text_of(outputs[a][k]) == text_of(outputs[b][k]) for k in common)
        w = sum(d >= args.tie for d in deltas.values())
        l_ = sum(d <= -args.tie for d in deltas.values())
        worst10 = sorted(deltas.values())[:10]
        L.append(f"| {a} vs {b} | {w} | {l_} | {len(common) - w - l_} | {ident} | "
                 f"{100 * statistics.mean(deltas.values()):+.2f} | {100 * sum(worst10) / len(common):+.2f} |")
        rows.append((a, b, deltas))
    L += ["", "Last column: contribution of the 10 most negative prompts to the mean Δ. If it is close to the mean, the loss is concentrated in a few prompts.", ""]

    L += ["## Do flagged step2 answers explain the loss?", "",
          "| Pair | step2 flag | Prompts | Mean Δ (pp) | Prompts without flag | Mean Δ without (pp) |", "|---|---|---:|---:|---:|---:|"]
    for a, b, deltas in rows:
        if a != "step2" or b not in ("step0", "bon15"):
            continue
        for fname, test in (("any residue", lambda x: bool(x["tags"] or x["meta"])),
                            ("truncation-like", lambda x: x["near_cap"] or x["no_terminal_punct"] or x["unclosed_fence"])):
            yes = [d for k, d in deltas.items() if test(flags["step2"][k])]
            no = [d for k, d in deltas.items() if not test(flags["step2"][k])]
            L.append(f"| step2 vs {b} | {fname} | {len(yes)} | {fmt(100 * statistics.mean(yes), 2) if yes else '—'} | "
                     f"{len(no)} | {fmt(100 * statistics.mean(no), 2) if no else '—'} |")
    L.append("")

    rm_rows = [(k, rm_of(outputs["step2"][k])) for k in keys]
    if all(v is not None for _, v in rm_rows):
        res = [v for k, v in rm_rows if flags["step2"][k]["tags"] or flags["step2"][k]["meta"]]
        clean = [v for k, v in rm_rows if not (flags["step2"][k]["tags"] or flags["step2"][k]["meta"])]
        L += ["## RM of step2 answers with vs without residue", "",
              f"With residue: n={len(res)}, mean RM {fmt(statistics.mean(res)) if res else '—'}; "
              f"without: n={len(clean)}, mean RM {fmt(statistics.mean(clean)) if clean else '—'}.", ""]

    L += ["## Judge usage", "", "| Stage | Requests with completion_tokens | Mean | Max | Reasoning-token fields | Max reasoning tokens |",
          "|---|---:|---:|---:|---:|---:|"]
    for s in STAGES:
        u = usage_stats(root, s)
        if u is None:
            L.append(f"| {s} | usage.jsonl missing | | | | |")
        elif not u["requests_with_completion_tokens"]:
            L.append(f"| {s} | 0 | — | — | — | — |")
        else:
            L.append(f"| {s} | {u['requests_with_completion_tokens']} | {u['mean_completion_tokens']:.2f} | "
                     f"{u['max_completion_tokens']} | {u['reasoning_tokens_seen']} | {fmt(u['max_reasoning_tokens'])} |")
    L.append("")

    (out_dir / "report.md").write_text("\n".join(L), encoding="utf-8")

    W = ["# Worst prompts for manual reading", ""]
    for a, b in WORST_PAIRS:
        deltas = next(d for x, y, d in rows if (x, y) == (a, b))
        W += [f"## {a} vs {b}: {args.worst} most negative Δ", ""]
        for rank, (k, d) in enumerate(sorted(deltas.items(), key=lambda kv: kv[1])[: args.worst], 1):
            fa, fb = flags[a][k], flags[b][k]
            marks = [m for m, on in (("TAG", fa["tags"]), ("META", fa["meta"]), ("NEAR-CAP", fa["near_cap"]),
                                     ("NO-END-PUNCT", fa["no_terminal_punct"]), ("UNCLOSED-```", fa["unclosed_fence"])) if on]
            W += [f"### {rank}. Δ = {100 * d:+.1f} pp · {a} {scores[a][k]:.2f} vs {b} {scores[b][k]:.2f} · "
                  f"{fa['chars']} vs {fb['chars']} chars · {', '.join(marks) or 'no flags'}", "",
                  f"**Instruction:** {k[0]}", "",
                  f"<details><summary>{b}</summary>\n\n{fenced(text_of(outputs[b][k]))}\n</details>", "",
                  f"<details open><summary>{a}</summary>\n\n{fenced(text_of(outputs[a][k]))}\n</details>", ""]
    (out_dir / "worst_cases.md").write_text("\n".join(W), encoding="utf-8")

    with open(out_dir / "per_prompt.csv", "w", newline="", encoding="utf-8") as f:
        wtr = csv.writer(f)
        wtr.writerow(["instruction", "occurrence"] + [f"{s}_{c}" for s in STAGES for c in
                     ("score", "chars", "tokens", "tags", "meta", "near_cap", "no_terminal_punct", "unclosed_fence")])
        for k in keys:
            row = [k[0], k[1]]
            for s in STAGES:
                fl = flags[s][k]
                row += [fmt(scores[s].get(k), 4), fl["chars"], fl["tokens"] or "", " ".join(fl["tags"]),
                        "; ".join(fl["meta"]), int(fl["near_cap"]), int(fl["no_terminal_punct"]), int(fl["unclosed_fence"])]
            wtr.writerow(row)

    (out_dir / "flags.json").write_text(json.dumps(
        {s: [{"instruction": k[0], "occurrence": k[1], **flags[s][k]} for k in keys] for s in STAGES},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(L))
    print(f"\nWrote {out_dir}/report.md, worst_cases.md, per_prompt.csv, flags.json")


if __name__ == "__main__":
    main()
