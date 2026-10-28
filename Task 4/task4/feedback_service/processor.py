"""Complaint processor (plan 3.5): turns a stored complaint into the textual critique TPO consumes.

Same logic as Task 3's localize_with_clarification, split over two HTTP exchanges: localize once; low
confidence asks the user one clarifying question instead of passing anything to TPO; still low after the
answer stops. With C switched off the critique is the raw complaint."""
from .bridge import CONFIGS
from tpo import context as ctx  # noqa: E402  (tpo is importable once .bridge has run)

DEFAULT_QUESTION = "Could you say more precisely what is wrong with the plan?"   # Task 3's fallback, verbatim
CRITIQUE_FIELDS = ("target", "aspect", "direction", "modification_type", "confidence", "threshold",
                   "corrected_value", "evidence")


class ComplaintProcessor:
    def __init__(self, engine):
        self.engine = engine

    def first_pass(self, fb):
        """Localization record in Task 3's shape; asked/question are set when a clarification is needed."""
        first = self.engine.localize(fb, None)
        loc = {"case_id": fb["feedback_id"], "run": 1, "initial": first, "asked": False, "question": None,
               "answer": None, "after_clarification": None, "final": first}
        if first.get("confidence") != "high":
            loc.update(asked=True, question=first.get("clarification_question") or DEFAULT_QUESTION)
        return loc

    def second_pass(self, fb):
        loc = dict(fb["localization"])
        second = self.engine.localize(fb, {"question": loc["question"], "answer": loc["answer"]})
        loc.update(after_clarification=second, final=second)
        return loc

    @staticmethod
    def ready(loc):
        return loc["final"].get("confidence") == "high"

    @staticmethod
    def critique(fb):
        """What TPO is told about the complaint before the first iteration (each iteration's prompt recomputes
        the evidence on its own input plan; the iteration log keeps that version)."""
        if not CONFIGS[fb["config"]].C:
            return {"source": "raw_complaint", "text": ctx.complaint_block(fb["complaint"]), "structured": None,
                    "clarification": None}
        loc = fb["localization"]
        c = loc["final"]["critique"]
        return {"source": "feedback_localization", "text": c.get("critique_text"),
                "structured": {k: c.get(k) for k in CRITIQUE_FIELDS},
                "clarification": {"question": loc["question"], "answer": loc["answer"]} if loc["asked"] else None}

    @staticmethod
    def summary(loc):
        """Prompt-free summary for events and views."""
        f = loc["final"]
        crit = f.get("critique") or {}
        return {"confidence": f.get("confidence"), "target": crit.get("target"),
                "modification_type": crit.get("modification_type"), "asked": loc["asked"],
                "question": loc["question"], "answer": loc["answer"]}
