"""Task 3's adapter over the Task 2 components, with Task 2's task2_v2.1 attribution and localization.

Same item format as tpo_v2; a plan over capacity on the data in force gives an item with the conclusion
"current_plan_infeasible" and no alternative (the loop never attributes such a plan: every input plan was committed
by the solver on the data in force)."""
from tpo_v2.components import Task2ComponentsV2

from v21 import attribution as attribution_v21    # Task 2's task2_v2.1 package (on sys.path via task2_bridge)
from v21 import localization as localization_v21


class Task2ComponentsV21(Task2ComponentsV2):
    def __init__(self, base, llm, run_label="t3-{run}", probe="v2"):
        super().__init__(base, llm, run_label, probe)
        self.att, self.loc = attribution_v21, localization_v21
