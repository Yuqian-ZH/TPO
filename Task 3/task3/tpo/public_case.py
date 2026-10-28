"""The only view of a test case that prompts may see (plan 3.2). Checker, thresholds, reference
modification, hand labels (clarity, complaint_object, why/what-if, gt) stay with the simulated user."""
from dataclasses import dataclass

PUBLIC_FIELDS = ("id", "solution", "complaint", "model_modifications")


@dataclass(frozen=True)
class PublicCase:
    id: str
    solution: dict
    complaint: str
    model_modifications: tuple


def public_view(case):
    return PublicCase(id=case["id"], solution={"routes": [list(r) for r in case["solution"]["routes"]]},
                      complaint=case["complaint"], model_modifications=tuple(case.get("model_modifications", ())))
