"""FeedbackServiceV3 with task3_v31's prompt: the session's own modifications are shown (DESIGN_V31.md section 2).

Order of the blocks: modifications the session was created with (tpo_v31.loop.session_block), then those accepted
with earlier complaints (ServiceTrial), then "Modifications currently in force". A session without either gets
task4_v3's prompt byte for byte."""
from feedback_service.bridge import CONFIGS, PublicCase, t2
from feedback_service.engine import SERVICE_SETTINGS, DeferredUser, ServiceTrial, thread_mods
from feedback_service.service import DEFAULT_CONFIG
from feedback_service.store import Store, random_id
from feedback_service.worker import CountingLLM
from feedback_service_v21.service import default_components_v21
from feedback_service_v3.service import EngineV3, FeedbackServiceV3
from tpo_v31.loop import session_block

PROTOCOL = "task4_v31"


class ServiceTrialV31(ServiceTrial):
    def __init__(self, *args, session=(), **kw):
        super().__init__(*args, **kw)
        self.session = list(session)

    def blocks(self):
        b, attr = super().blocks()
        if self.session:
            b["mods_in_force"] = session_block(self.session) + "\n\n" + b["mods_in_force"]
        return b, attr


class EngineV31(EngineV3):
    def trial(self, fb):
        """As EngineV3.trial, with the session's modifications shown."""
        pc = PublicCase(id=fb["feedback_id"], solution={"routes": [list(r) for r in fb["solution"]["routes"]]},
                        complaint=fb["complaint"], model_modifications=tuple(thread_mods(fb)))
        tr = ServiceTrialV31(pc, self.base, DeferredUser(), CONFIGS[fb["config"]], fb["config"], 1, self.comps,
                             self.llm, self.settings, loc=fb.get("localization"),
                             accepted=fb["accepted_modifications"], session=fb["session_modifications"])
        st = fb.get("trial")
        if st:
            tr.history = st["history"]
        return tr


class FeedbackServiceV31(FeedbackServiceV3):
    def health(self):
        return {**super().health(), "protocol": PROTOCOL}


def build_service_v31(data_dir, llm=None, components_factory=default_components_v21, new_id=random_id,
                      default_config=DEFAULT_CONFIG, settings=SERVICE_SETTINGS, startup_checks=None):
    """As build_service_v3, with EngineV31 and FeedbackServiceV31."""
    base = t2.load_frozen_instance()
    store = Store(data_dir, new_id)
    if llm is None:
        from tpo.llm import real_client
        llm = real_client(store.llm_log_path())
    counting = CountingLLM(llm)
    engine = EngineV31(base, components_factory(base, counting), counting, settings)
    return FeedbackServiceV31(store, engine, counting, default_config=default_config, startup_checks=startup_checks)
