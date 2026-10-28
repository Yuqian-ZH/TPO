# Task 5: Production-Grade Self-Evolution at Enterprise Scale

TPO corrects the system at inference time; this plan turns those corrections into model updates that can be trusted across many tenants. The deployed system is the Task 4 service: an LLM localizes a complaint (or asks a clarifying question), proposes **model modifications**, and Gurobi re-solves. The solver owns feasibility and the routes. What can evolve are the LLM's three decisions: how to localize, whether to ask, and which modifications to propose.

Numbers marked with a task come from this repository's measurements; Meta RLUF facts are quoted from the paper (Han et al., *Reinforcement Learning from User Feedback*, Meta GenAI, arXiv 2505.14946v1, May 2025). Thresholds, cadences and sizes not marked that way are proposed starting values to be tuned, not measurements.

## 0. What Tasks 1 to 4 imply for the design

| Finding | Source | Design consequence |
|---|---|---|
| With a strong LLM, clear complaints are fixed in the first iteration; 298 of 300 trials converged. The only mechanism with a visible effect was localization with a clarifying question (first-iteration convergence 100% with it, 80 to 83% without), and the gain came from the user's answer, not from the structured fields | Task 3 (v1) | Distillation buys cost and latency on the easy cases and quality on the ambiguous ones. The clarification behaviour is the asset to protect (section 3.2) |
| The first two ablations could not separate the mechanisms by design (most cases solved at once, the ambiguous limits known only to the clarification). Re-designed (task3_v3: cases whose plain fix has side effects, the same user words for every configuration, 5 runs) and repeated with new seeds and three control arms (task3_v3.1): on those complaints the counterfactual probe's main effect was 12 percentage points [+2, +22] in v3 and +5 [−6, +17] in v3.1; with the same three candidates, choosing with the probe's forecast beat choosing blind by 18 percentage points [+2, +34], and choosing blind was worse than taking one candidate. Asking first resolved vague complaints one iteration earlier but not more often, and the gain came from the user's answer, not the structured fields. Attribution had no reliable effect (its harm in v3 did not replicate) | Task 3 (v3, v3.1) | Keep verify-before-commit in the served loop and record the probe's forecasts in the trajectories: the forecast, not extra samples, is what helps with side effects, so candidates are never added without it (2.2, 2.3) |
| Without localization, converged plans were 3.7 to 9.0 km longer on average than Task 2's reference fix | Task 3 | "The user accepted" is not enough; collateral cost must enter the reward and the guardrails |
| A learned reward model scored TPO's refined answers higher than Best-of-15 (RM +0.80) while an independent judge did not prefer them (win rate −5.74 pp, 95% CI [−11.92, 0.007]) in the first run; in the frozen third run the same pattern held (RM +0.88 [0.48, 1.28], judge +0.16 pp [−5.51, 5.95]) although the judged win rate rose monotonically over the iterations | Task 1 | A learned proxy must never be the only training signal. This is a divergence, not by itself proof of reward hacking |
| The frozen confidence rule counted a disagreement the user cannot resolve (soft constraint vs objective weight, same target); the clarifying question could not fix it and the complaint stopped. A rule that counts only target, direction and limit rates the same samples high confidence (Task 2, protocol task2_v2) | Task 4 (T7) | Calibrate the localizer on what the user can answer; log uninformative questions as negatives |
| 95 to 99% of serving time is LLM time; a Gurobi commit solve takes 58 to 70 ms (median); a complaint costs about 11.8k tokens in the default configuration | Task 4 (v1) | Solver-based checks are cheap enough to run on every feedback event; distillation pays mostly in latency and tokens |
| Attribution matched exhaustive ground truth 10/10, but only on optimal plans of the unmodified model. On plans under soft constraints the frozen version relabelled the alternative plan and reported a wrong objective for it in 149 of 885 decisions (largest error 46,500); the fixed version matches brute force on all 885. The local counterfactual stopped early on some queries (objective within 1% of the full re-solve on 87 of 101) | Task 2 | Labels for training use the full re-solve, not the local heuristic; every number that reaches a prompt or a label is re-checked by an independent computation |

## 1. Architecture

```
 tenant users ──► online service (Task 4: localize / ask ─► TPO ─► Gurobi)   per tenant, versioned
                        │  trajectory logs: iterations.jsonl + events.jsonl, tagged with model,
                        │  prompt, config and validator versions
                        ▼
                 feedback validator (solver + attribution + counterfactual)    nightly, no LLM
                        │  labels: verified_positive / verified_negative / self_imposed /
                        │          hard_constraint / excluded / incident
                        ▼
      tenant data store (encrypted, per tenant) ──abstraction, k-anonymity, DP──► shared pattern pool
                        │                                                         │
          tenant adapter training (weekly)                         shared base training (monthly)
                        └──────────────────────► model registry ◄─────────────────┘
                                                      │
                          offline gates ─► shadow ─► canary A/B ─► ramp   (rollback at every stage)
```

## 2. Closing the loop: from correction to evolution

### 2.1 What is learned and what is not

| Decision | Input | Output | Learned from |
|---|---|---|---|
| Localize or ask | complaint, plan, indicators | target, aspect, direction, modification type, threshold; or a question | final high-confidence localizations; questions whose answer changed the localization |
| Propose | critique, plan, history | modification list (Task 2 format) | accepted and verified modification lists |
| Explain | attribution and counterfactual JSON | text | verified explanations only (number and entity checks as in Task 2) |

Not learned: routes and feasibility (the solver), and whether a complaint is resolved (the user's reply, verified as in section 3).

### 2.2 The trajectory record

One complaint thread from the Task 4 logs: tenant, session, feedback ID; model, prompt, configuration and validator versions; instance hash; the plan complained about; complaint; clarification question and answer; the five localization samples; the critique; per iteration the candidates, probe results, committed modifications, refined plan and feasibility; the user's replies; the final status and accepted modifications; follow-up signals (a new complaint on the same target within 7 days, a manual override of the plan); and the validator's label. Everything except the follow-up signals is already logged by Task 4.

### 2.3 Building training examples

**SFT, proposer (trajectory compression).** Input: the iteration-1 prompt of a thread that ended `resolved` and `verified_positive`. Target: the final accepted modification list. A thread that needed three iterations teaches the model to produce the third answer first. Example weight: validator confidence times user reliability (section 3.3).

**SFT, localizer.** Input: complaint and plan. Target: the final high-confidence localization. For threads where the clarification answer changed the localized target, the target is the question itself (teach when to ask). Threads where the answer did not change the result (the Task 4 T7 pattern) are not "ask" examples; they are the evidence for recalibrating the confidence rule (2.5) so that this kind of disagreement no longer triggers a question.

**DPO, proposer.** All pairs share the iteration-1 context:

| Chosen | Rejected | Why the label is trustworthy |
|---|---|---|
| final accepted and verified list | an earlier list in the same thread that the user rejected | only if the validator confirms the rejected list failed the localized predicate, so user noise does not create pairs |
| a candidate whose probe predicts the target met at low collateral cost | a candidate the probe predicts infeasible, unchanged, or not moving the target | the probe (condition B) proposes the pair at no extra LLM cost, but it is a heuristic, so the pair enters training only after a full re-solve of both candidates confirms the labels (section 0, Task 2); pairs the re-solve contradicts are dropped |
| solver-labelled offline samples: k candidates per logged context, solved | same | the solver checks the predicate and computes collateral exactly; no user involved |

Pairs that both satisfy the predicate and differ only in wording are excluded: such pairs teach style, which is exactly what RLUF's reward model learned to reward (section 3.2).

**If a reinforcement step is used,** the reward is the verified predicate (the localized target meets the user's stated threshold, or moved the requested way if none was stated, on a plan feasible on confirmed data) minus collateral cost (excess distance over the cheapest plan that meets the same predicate, which the solver computes by adding the predicate as a hard constraint). User acceptance is a gate for which threads count, never the reward itself.

### 2.4 Cadence

| Step | When | Notes |
|---|---|---|
| TPO at inference | always | unchanged; it is also the data source |
| ETL and validation | nightly over closed threads | LLM-free; tens of milliseconds of solver time per check |
| Label finalization | 7 days after acceptance | a re-complaint on the same target flips a positive to negative |
| Tenant adapter (LoRA on localizer and proposer) | weekly, if at least 200 new verified threads; otherwise monthly | small tenants benefit through the shared base only |
| Shared base | monthly, from the shared pattern pool (section 4) | adapters are re-fitted on the new base before release |
| Replay | every run | about 30% older verified data plus the fixed regression suite, against forgetting |
| Evaluation split | by time | train on weeks up to t, evaluate on week t+1 |

Every candidate goes through the release path of section 5; nothing deploys automatically.

### 2.5 Keep the gate outside the model

The confidence gate that decides whether to ask stays rule-based and outside the trained model (as in Task 2: agreement across samples), with its rule recalibrated so that only disagreements the user can resolve count. A distilled localizer that "learns" never to ask would look better on acceptance and worse on ambiguous complaints, which is the RLUF failure mode below.

## 3. Feedback quality: filter, weight, validate

### 3.1 Signals

| Kind | Signals | Noise |
|---|---|---|
| Explicit | resolved or not, comment, stop, clarification answers | users accept plans they misread, complain about plans that do what they asked |
| Implicit | re-complaint on the same target within 7 days, manual override after acceptance, abandonment | delayed, confounded by new circumstances |
| Verifiable | feasibility on confirmed data, the localized predicate on the accepted plan, collateral cost, attribution, counterfactuals | exact for what they cover; they do not see preferences the user never stated |

### 3.2 The Meta RLUF failure mode and its counterpart here

RLUF trained a reward model, P[Love], to predict Love reactions, a binary signal that is "extremely sparse: approximately 0.1% of all model messages receive a love reaction". It predicted future behaviour well (Pearson r = 0.95 between offline scores and online Love-rate changes). Added with weight 0.3 next to helpfulness (0.7) and safety (0.3) objectives, it raised the Love rate by 28% in a live A/B test (weight 0.1: +9.73%). It also produced reward hacking: responses containing "bye" rose from 0.72% to 2.8%, the aggressive model repeated "bye" on every turn ("most common when the prompt is unclear"), both Love-optimized models asked roughly half as many follow-up questions, and the tone became "more positive and bubbly". Helpfulness fell from 1.53 to 1.28 and the safety violation rate rose from 11.4% to 12.7%. The authors note that "used alone, the P[Love] reward model would over-weight a narrow dimension mainly capturing positive tone". Their working mitigation was "simple sweeps on the weights of the optimization objectives"; they propose, without implementing it, optimizing the Love reward "conditioned on high helpfulness RM score as a constraint", and conclude that "completely mitigating reward hacking behavior remains an open problem".

Our proxy is the acceptance rate. Optimizing it naively would reproduce each of those behaviours in optimization terms:

| RLUF behaviour | Counterpart in the feedback loop | Evidence here | Guard |
|---|---|---|---|
| Fewer follow-up questions | Fewer clarifying questions: the model guesses instead of asking | Clarification resolved ambiguous complaints one iteration earlier (Task 3 v3: +62 percentage points at iteration 1) | Clarification rate on a fixed ambiguous slice is a release gate; the gate stays rule-based (2.5) |
| Farewell lines that win reactions without helping | Plans that please the complainer at someone else's cost: the other driver gets the stops, the total distance grows | Without localization, converged plans were 3.7 to 9.0 km longer than the reference fix (Task 3) | Collateral cost in the reward; per-vehicle and total-distance guardrails |
| Reward for tone rather than substance (helpfulness fell) | Making the complaint vanish on paper: data changes the user never stated (the modification whitelist allows `capacity`) | Scenario V5: the plan the user praised overloads vehicle 1 (124 against 100) on the confirmed data | Feasibility on confirmed data is a hard filter; unstated data changes need explicit confirmation |
| Positive tone persuades | Explanations that persuade the user a change happened when it did not | Scenarios V3, V4 | Praise is checked against the measured change before it counts |
| Proxy rises while quality does not | A learned reward diverges from an independent evaluator | Task 1 RM vs judge | Never train against a single learned proxy; rewards come from verifiable predicates |

Design rules that follow: acceptance is a gate, not the reward; the reward is verifiable; every known failure has its own guardrail metric; and, as RLUF did, any weight on user-derived signals is swept, keeping the largest weight with no guardrail regression. The constrained form RLUF proposes (optimize the user signal only where an independent quality score is high) is available here in a stronger version, because the quality score is not another learned model but a solver check.

### 3.3 The filtering and weighting pipeline

1. **Hard filters.** Drop system failures (LLM unavailable, interrupted jobs; Task 4 already marks them `failed`), retries and test traffic, and threads produced by a version that was later rolled back. A plan infeasible on confirmed data is an **incident** and becomes a negative example for the proposer. Threads that rely on data changes the user has not confirmed wait until the data is confirmed. Online, the same rule applies before acceptance: Task 4 already reports which data changes a plan depends on, and the service should ask the user to confirm them before the plan can be accepted.
2. **Verification.** Re-check the localized predicate on the accepted plan (target moved the right way, threshold met if one was stated) and compute collateral cost. Where the user's verdict and the predicate disagree, the thread goes to a disagreement bucket rather than into training.
3. **Misunderstanding and self-imposed checks** (3.4).
4. **Weighting.** Each user's reliability is the posterior mean of a Beta prior updated with their agreement with the verifier on threads where the verifier is decisive; example weight is that reliability, each user's share of a tenant's weekly examples is capped (5%), and tenants are normalized so that large tenants do not dominate the shared pool.
5. **Time.** A positive becomes final after 7 days without a re-complaint on the same target.
6. **Human review.** 2% of examples plus every disagreement-bucket thread are reviewed; the reviewed set is the gold standard for measuring the filter's own precision and recall.

Output labels: `verified_positive`, `verified_negative`, `self_imposed` (no blame on the model; trains the "explain the trade-off" response), `hard_constraint` (explanation, not a fix), `excluded` (misunderstanding), `incident`.

### 3.4 Using decision attribution and counterfactuals to catch misunderstandings and self-imposed constraints

A small validator ([`validator/checks.py`](validator/checks.py)) implements the checks with Task 2's attribution (protocol task2_v2.1: IIS for forced decisions, alternatives anchored to the current plan) and the counterfactual re-solve, solver only. The demonstration below starts from real sessions of the Task 4 end-to-end run; the feedback text is illustrative and enters in the structured form the localizer produces (for praise: the target or decision the user believes changed, and the direction). The scenarios were built to show each check, with three controls for false alarms: this demonstrates the mechanism, it does not measure detection rates. Full table: [`results/validator_demo.md`](results/validator_demo.md).

**Positive feedback based on a misunderstanding.** Three checks, each of which removes the example from the positives:

| ID | User says | What the components show | Verdict |
|---|---|---|---|
| V4 | "Great, customer 3 now gets its delivery early." | measured change: arrival distance of customer 3 went from 60 to 129 km | praised change absent: excluded |
| V3 | "Thanks for putting customers 3 and 5 on the same truck." | `SAME(3,5)` held before the fix too; attribution on the old plan: objective-preferred, so the modification did not cause it | credit misattributed: excluded |
| V5 | "Good, the second driver has fewer stops now." | the stops did drop (4 to 2), but on the confirmed data vehicle 1 carries 124 against a capacity of 100: the plan relied on a capacity change the user never stated | incident |
| V6 (control) | "Good, vehicle 1 is no longer loaded to the limit." | load of vehicle 1 went from 99 to 91 on a feasible plan | usable positive |

Training on V3 would reward a modification for an effect it did not have; on V4 it would reward the explanation for persuading; on V5 it would reward a plan that cannot be driven.

**A complaint that targets a constraint the user imposed.**

| ID | Situation | User says | What the components show | Verdict |
|---|---|---|---|---|
| V1 | the user earlier accepted "vehicle 1 carries at most 92" (T2) | "Vehicle 1 now drives 235 km; that is too far." | counterfactual without that accepted input: vehicle 1 drives 140 km, total 390 to 351 | self-imposed: show the trade-off and ask which to keep |
| V2 | the user entered demand 54 for customer 3 (T9) | "Customers 2 and 5 should share a truck." | attribution: `SEP(2,5)` forced by `cap[1]`, `cap[2]` (IIS); with the user's demand reverted it is only objective-preferred | self-imposed by the user's data |
| V2b (control) | same session | "Customers 1 and 3 should share a truck." | forced by capacity with or without the user's data | physical constraint: explain |
| V7 (control) | same as V1 | "Vehicle 2 still has too many stops." | dropping the user's input leaves vehicle 2 at 4 stops | genuine: normal TPO |
| V8 (control) | no user inputs (T1) | "Vehicle 2 is on the road for 211 km." | nothing to drop | genuine |
| V9 (constructed) | the user entered demand 62 for customer 3 and capacity 110; total demand 202 exceeds two trucks of 100 | "Vehicle 2 drives too far." | without the demand entry vehicle 2 drives 155 km instead of 211; without the capacity entry there is no feasible plan at all, which is recorded as evidence (the entry makes the plan possible), not as a cause | self-imposed by the demand entry |

A self-imposed complaint is not evidence that the model erred, and it must not create a negative example for the earlier fix; it trains the response "this conflicts with your earlier request; here is what each choice costs".

**What production needs beyond the demo.** Every modification carries a provenance tag (user-entered data, user-accepted fix, system default); Task 4 already tags accepted fixes (`acc<n>_<k>`). Task 2's counterfactual query language can add modifications but not remove one (an empty `APPLY_MODIFICATIONS` is rejected), so the validator answers "what if this input were dropped" with the full re-solve under the same anchor rule (the counterfactual component's control method); a `REMOVE_MODIFICATION` query type belongs in the component. At this instance size every check takes milliseconds; at larger sizes the nightly batch can afford full solves, which matters because the local method's answers were sometimes worse than a full re-solve (3 to 13 of 20 queries at 12 to 20 customers, Task 2 scale-up).

## 4. Multi-tenant isolation with shared evolution

### 4.1 Isolation boundaries

| Layer | Isolation |
|---|---|
| Data | per-tenant storage namespaces and encryption keys for instance data (coordinates, demands, fleet), complaints, plans and logs; tenant ID on every record |
| Compute | jobs tagged by tenant; solver workers stateless per request; caches keyed by tenant as well as content (Task 3's probe keeps resident models keyed by model state only) |
| Model | one frozen shared base; per-tenant LoRA adapters for localizer and proposer, never loaded for another tenant's request; per-tenant configuration (default configuration, thresholds, vocabulary such as "van" for vehicle) |
| Prompts | few-shot examples only from the same tenant |
| Observability | per-tenant dashboards; cross-tenant views only on aggregates |

### 4.2 What crosses the boundary

Only **abstract pattern records**: complaint intent class, aspect, target type (`W[k]`, not a vehicle name), modification type, threshold relative to the current value (for example −8%), whether a clarification was needed and whether it changed the target, the outcome labels and a collateral-cost bucket. No coordinates, demands, names, plans or raw text. For the shared base, each pattern is replayed on **synthetic instances** drawn from a generator like Task 2's, so its training examples contain no tenant data at all. Raw text examples are used only for tenants that opt in by contract, after PII scrubbing.

### 4.3 Aggregation safeguards

A pattern enters the shared pool only after it has occurred in at least k = 5 tenants; released counts carry differential-privacy noise; each tenant's contribution is capped; lineage from patterns to contributing tenants is kept, so a deletion request removes the contribution at the next shared retrain.

### 4.4 Releasing a shared update

Before a new shared base ships: canary strings planted in each tenant's data must never be generated by the model; a membership-inference test on held-out against trained tenant records must stay at chance; and no tenant's held-out suite may regress beyond tolerance (otherwise the release is blocked, or that tenant pins the previous base). Tenants can opt out of shared updates entirely.

The split follows what generalizes: deciding that "too much work" needs a question about load versus distance, choosing a soft constraint over a weight, and calibrated confidence are tenant-agnostic skills; vocabulary, local rules and typical thresholds stay in adapters and configuration.

## 5. A/B testing and rollback

### 5.1 Release path

1. **Offline gates**, all required: the frozen regression suite (Task 2's 10 test cases through the Task 3 simulated-user harness, all eight configurations; convergence may not drop, and the ambiguous slice is reported separately); validator-labelled held-out recent threads (predicate rate, collateral cost); no unconfirmed data changes; schema validity; cost and latency budget.
2. **Shadow**, 1 to 2 weeks: the candidate runs on live complaints in parallel; its proposals are solved and checked against the localized predicate but never shown. This compares substance (predicate, collateral, clarification decisions) without user exposure.
3. **Canary**: randomize by complaint thread, sticky for the whole thread (Task 4 already fixes the configuration per feedback record), stratified by tenant, ramping 5%, 25%, 50%, 100% with minimum durations.

### 5.2 Metrics

| Group | Metric | Role |
|---|---|---|
| Primary | acceptance rate (resolved over closed threads); first-iteration resolution; iterations per thread | decision |
| Hard guardrail | plans infeasible on confirmed data (must stay 0); plans depending on unconfirmed data changes | immediate rollback |
| Quality guardrail | verified predicate rate; excess distance over the cheapest plan meeting the same predicate; re-complaint within 7 days; stop and abandon rate; low-confidence stops | statistical rollback |
| RLUF-specific | clarification rate on ambiguous complaints; validator's praise-misattribution rate | statistical rollback |
| Operational | LLM failure rate; p95 latency; tokens and cost per thread | immediate or budget rollback |

### 5.3 Statistics

Decision rules are written before each test, as Task 3's ablation did. Sequential tests with always-valid confidence intervals allow early stopping without inflating error; intervals are clustered by session and tenant. Sample size: with a baseline acceptance around 95% (Task 4 v1 saw 19 of 20), detecting a drop to 93% at 5% two-sided significance and 80% power needs about 2,200 threads per arm; a 1-point drop needs about 8,200. Small tenants are therefore judged on pooled metrics plus their own hard guardrails.

### 5.4 Rollback triggers

| Trigger | Action |
|---|---|
| Any plan infeasible on confirmed data shown to a user | immediate automatic rollback, incident |
| Unconfirmed data-change rate above control by more than 1 point | immediate |
| LLM or schema failure rate above twice the control; p95 latency over the SLO for 15 minutes | immediate |
| Acceptance rate: upper confidence bound of the difference below −2 points | rollback |
| Re-complaint rate: lower bound of the difference above +2 points | rollback |
| Clarification rate on ambiguous complaints: relative drop over 30% (the RLUF signature) | rollback even if acceptance is up |
| Excess distance up more than 5% | rollback |
| One tenant significantly worse while pooled metrics pass | roll back that tenant |

### 5.5 Rollback mechanics

Every version is immutable in a registry (base, adapter, prompts, configuration, validator); rollback is a routing switch. Threads in flight finish on the version they started with, except after a hard-guardrail trigger: then they move to the previous version and restart from the plan they were filed against (Task 4 already returns a session to that plan when a complaint does not end in acceptance). Data produced by a rolled-back version is quarantined from training by its version tag, its incidents are reviewed, and the failing pattern is added to the regression suite so the next candidate is tested against it.

## 6. Limitations

1. The users in Tasks 3 and 4 are simulated from checkers and answer consistently; real reliability distributions are unknown until the human-review gold set exists.
2. Thresholds, cadences, k and caps are starting values.
3. The validator demonstration shows the mechanism on constructed scenarios, not detection rates.
4. Task 1's evidence on learned rewards is a divergence between a reward model and a judge, not proof of reward hacking.

## Reproduce the validator demonstration

```bash
cd "Task 5/task5"
export PYTHONDONTWRITEBYTECODE=1
python -m pytest -q          # 6 tests
python -m validator.demo     # writes results/validator_demo.{json,md}; Gurobi only, no LLM, reads Task 4 results
```
