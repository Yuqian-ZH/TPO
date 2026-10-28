"""TPO refinement loop (plan 3). Trial.step() is one iteration; run_trial() drives up to D iterations
against the simulated user. Task 4 calls step() once per complaint it receives."""
import time
from dataclasses import asdict, dataclass

from . import context as ctx
from .commit import commit_solve, tie_diagnostic
from .entities import decisions, extract
from .llm import PROTOCOL, derive_seed
from .proposal import assign_ids, parse_choice, parse_proposal
from .public_case import public_view
from .task2_bridge import apply_data_mods, canon
from .user_sim import NOTE_NO_PLAN, NOTE_REJECTED, SimulatedUser


@dataclass(frozen=True)
class Flags:
    A: bool
    B: bool
    C: bool
    blind: bool = False       # S1: B's candidates and selector, but no probing
    clar_text: bool = False   # S2: raw complaint plus the clarification answer, no localization


CONFIGS = {f"A{a}B{b}C{c}": Flags(bool(a), bool(b), bool(c)) for a in (0, 1) for b in (0, 1) for c in (0, 1)}
MAIN = tuple(CONFIGS)
CONFIGS["S1"] = Flags(True, True, True, blind=True)
CONFIGS["S2"] = Flags(True, True, False, clar_text=True)


@dataclass(frozen=True)
class Settings:
    max_iters: int = 3
    n_candidates: int = 3
    propose_temperature: float = 0.7
    propose_max_tokens: int = 800
    select_temperature: float = 0.0
    select_max_tokens: int = 200
    tie_diagnostic: bool = True


def needs_localization(flags):
    return flags.C or flags.clar_text


def localize_with_clarification(case, base, comps, run):
    """Shared by every configuration of the same (case, run): one localization, one clarification at most."""
    pc, user = public_view(case), SimulatedUser(case, base)
    args = (list(pc.model_modifications), pc.solution, pc.complaint)
    first = comps.localize(*args, None, run, pc.id)
    rec = {"case_id": pc.id, "run": run, "initial": first, "asked": False, "question": None, "answer": None,
           "after_clarification": None, "final": first}
    if first.get("confidence") == "high":
        return rec
    q = first.get("clarification_question") or "Could you say more precisely what is wrong with the plan?"
    ans = user.clarify(q)
    second = comps.localize(*args, {"question": q, "answer": ans}, run, pc.id)
    rec.update(asked=True, question=q, answer=ans, after_clarification=second, final=second)
    return rec


def _strip_ids(mods):
    return [{k: v for k, v in m.items() if k != "id"} for m in mods]


def _llm_meta(out):
    return {k: out.get(k) for k in ("parse_status", "usage", "latency_s", "returned_model", "attempts",
                                    "reasoning_present")}


def _compact(a):
    """Prompt-facing part of a component output: no raw payload, no empty fields."""
    return {k: v for k, v in a.items() if k != "raw" and v not in (None, [], {})}


class Trial:
    def __init__(self, pc, base, user, flags, config, run, comps, llm, settings, loc=None):
        self.pc, self.base, self.user, self.flags = pc, base, user, flags
        self.config, self.run, self.comps, self.llm, self.settings, self.loc = config, run, comps, llm, settings, loc
        self.sol = pc.solution
        self.mods = []
        self.history = []
        self.sys_propose = ctx.system_prompt("proposal")
        self.sys_select = ctx.system_prompt("selector")

    def data(self):
        """Data the system currently believes: case model modifications + data modifications in force."""
        return apply_data_mods(self.base, list(self.pc.model_modifications) + self.mods)

    def model_mods(self):
        return list(self.pc.model_modifications) + self.mods

    def attribution(self):
        ent = extract(self.pc.complaint, self.base["n"], self.base["K"])
        decs = decisions(self.sol, ent)
        items = [self.comps.attribute(self.model_mods(), self.sol, d) for d in decs]
        return {"entities": ent, "decisions": decs, "items": items}

    def blocks(self):
        data = self.data()
        b = {"instance": ctx.instance_block(data), "plan": ctx.plan_block(self.sol, data),
             "mods_in_force": ctx.mods_block(_strip_ids(self.mods)), "history": ctx.history_block(self.history)}
        extra = self.loc["answer"] if self.flags.clar_text and self.loc["asked"] else None
        b["complaint"] = ctx.complaint_block(self.pc.complaint, extra)
        attr = None
        if self.flags.C:
            if self.loc["asked"]:
                b["clarification"] = ctx.clarification_block(self.loc["question"], self.loc["answer"])
            crit = self.comps.refresh_critique(self.loc["final"]["critique"], self.model_mods(), self.sol)
            b["localization"] = ctx.localization_block(crit)
        if self.flags.A:
            attr = self.attribution()
            b["attribution"] = ctx.attribution_block([_compact(a) for a in attr["items"]], self.sol, data)
        return b, attr

    def _meta(self, t, role, sample):
        return {"case_id": self.pc.id, "config": self.config, "run": self.run, "iteration": t, "role": role,
                "sample": sample}

    def propose(self, t, sample, msg):
        seed = derive_seed(self.pc.id, self.config, self.run, t, "propose", sample)
        out = self.llm.chat([{"role": "system", "content": self.sys_propose}, {"role": "user", "content": msg}],
                            temperature=self.settings.propose_temperature, seed=seed, json_mode=True,
                            max_tokens=self.settings.propose_max_tokens, meta=self._meta(t, "propose", sample))
        p = parse_proposal(out, self.base["n"], self.base["K"])
        return {"sample": sample, "seed": seed, "llm": _llm_meta(out), "content": out.get("content"), **p}

    def select(self, t, b, pool):
        msg = ctx.user_message(b, ctx.candidates_block(pool, self.flags.blind) + "\n\n" + ctx.TASK_SELECTOR)
        seed = derive_seed(self.pc.id, self.config, self.run, t, "select", 0)
        out = self.llm.chat([{"role": "system", "content": self.sys_select}, {"role": "user", "content": msg}],
                            temperature=self.settings.select_temperature, seed=seed, json_mode=True,
                            max_tokens=self.settings.select_max_tokens, meta=self._meta(t, "select", 0))
        ch = parse_choice(out, len(pool))
        return {"called": True, "seed": seed, "prompt": msg, "llm": _llm_meta(out), "content": out.get("content"),
                **ch}

    def step(self, t):
        t0 = time.perf_counter()
        b, attr = self.blocks()
        msg = ctx.user_message(b, ctx.TASK_PROPOSAL)
        rec = {"t": t, "input_solution": self.sol, "mods_before": _strip_ids(self.mods),
               "blocks": [k for k in ctx.ORDER if b.get(k)], "proposal_prompt": msg, "attribution": attr}
        n = self.settings.n_candidates if self.flags.B else 1
        cands = [self.propose(t, s, msg) for s in range(n)]
        rec["candidates"] = cands
        valid = [c for c in cands if c["valid"]]
        chosen, rec["selection"] = None, None
        if self.flags.B and valid:
            pool = valid
            if not self.flags.blind:
                for c in valid:
                    c["probe"] = self.comps.probe(list(self.pc.model_modifications), self.sol, c["modifications"])
                pool = [c for c in valid if c["probe"]["feasible"]] or valid
            if len(pool) == 1:
                rec["selection"] = {"called": False, "index": 0}
            else:
                rec["selection"] = self.select(t, b, pool)
            chosen = pool[rec["selection"]["index"]]
            rec["chosen_sample"] = chosen["sample"]
        elif valid:
            chosen = valid[0]
            rec["chosen_sample"] = chosen["sample"]

        new_sol, mods, note = self.sol, None, None
        if chosen is None:
            status = "rejected"
            errs = sorted({e for c in cands for e in c["errors"]})
            note = NOTE_REJECTED.format(errors="; ".join(errs))
        else:
            mods = assign_ids(chosen["modifications"], t)
            commit = commit_solve(self.base, self.pc.model_modifications, self.sol, mods)
            rec["commit"] = {k: v for k, v in commit.items() if k != "solution"}
            if commit["status"] == "optimal":
                status, new_sol = "committed", commit["solution"]
                if self.settings.tie_diagnostic:
                    rec["tie"] = tie_diagnostic(self.base, self.pc.model_modifications, self.sol, mods,
                                                self.user.resolved, commit)
                if chosen.get("probe"):
                    rec["probe_vs_commit"] = probe_agreement(self.sol, chosen["probe"], commit)
            else:
                status, note = "no_plan", NOTE_NO_PLAN
            rec["illegal_data_mods"] = self.user.illegal_data_mods(mods)
        if status == "committed":
            self.mods = mods
        verdict = self.user.verdict(new_sol)
        self.sol = new_sol
        rec.update(status=status, note=note, committed_mods=_strip_ids(mods) if status == "committed" else None,
                   solution_after=new_sol, verdict=verdict)
        if verdict["resolved"]:
            rec["label_swap_resolved"] = self.user.label_swap_resolved(new_sol)
        else:
            fb = self.user.feedback(verdict)
            h = {"t": t, "status": status, "mods": _strip_ids(mods or []), "feedback": fb, "note": note}
            if status == "committed":
                h["plan_lines"] = ctx.plan_lines(new_sol, self.data())
            self.history.append(h)
            rec["feedback"] = fb
        rec["wall_s"] = round(time.perf_counter() - t0, 4)
        return rec


def probe_agreement(cur_sol, probe, commit):
    """Same three agreement notions as Task 2's counterfactual evaluation."""
    if not probe["feasible"]:
        return {"feasible": commit["status"] != "optimal", "objective_1pct": None, "change_set": None}
    tol = 0.01 * max(1.0, abs(commit["objective"]))
    same_cs = (canon.change_key(canon.change_set(cur_sol, probe["solution"])) ==
               canon.change_key(canon.change_set(cur_sol, commit["solution"])))
    return {"feasible": True, "objective_1pct": abs(probe["objective"] - commit["objective"]) <= tol,
            "change_set": same_cs}


def run_trial(case, base, flags, config, run, comps, llm, settings=Settings(), loc=None):
    pc, user = public_view(case), SimulatedUser(case, base)
    rec = {"protocol": PROTOCOL, "case_id": pc.id, "config": config, "run": run, "flags": asdict(flags),
           "settings": asdict(settings), "localization": loc if needs_localization(flags) else None,
           "iterations": []}
    if needs_localization(flags) and loc is None:
        raise ValueError(f"{config} needs the shared localization of ({pc.id}, run {run})")
    if flags.C and loc["final"].get("confidence") != "high":
        rec.update(outcome="stopped_low_confidence", converged=False, converged_at=None,
                   final_solution=pc.solution, final_mods=[])
        return rec
    trial = Trial(pc, base, user, flags, config, run, comps, llm, settings, loc)
    for t in range(1, settings.max_iters + 1):
        it = trial.step(t)
        rec["iterations"].append(it)
        if it["verdict"]["resolved"]:
            rec.update(outcome="converged", converged=True, converged_at=t)
            break
    else:
        rec.update(outcome="not_converged", converged=False, converged_at=None)
    rec.update(final_solution=trial.sol, final_mods=_strip_ids(trial.mods))
    return rec
