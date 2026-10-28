# Task 1 methodology and monotonicity review

Reviewed 2026-10-20. Evidence: current official-repository implementation, saved raw candidates, all five evaluation stages, original judge log probabilities, and the paper. Additional CPU checks: [check_methodology.py](check_methodology.py), with results in [methodology_checks.json](methodology_checks.json). No generation or judge API calls were made.

**Conclusion: the core TPO implementation, stage extraction, and weighted-Qwen preference parsing are consistent with the intended procedure. This is an adapted replication with a negative independent-evaluation result. Monotonic independent win-rate improvement is an empirical target, not an algorithmic guarantee. Several interpretations in the project notes should be made more cautious.**

## What is guaranteed to be monotonic

For a prompt x, let C_t contain every retained candidate and its stored reward score through iteration t. The implementation adds candidates and selects the answer with the largest stored reward:

`C_(t+1) = C_t ∪ new_candidates`

`R_selected(t+1) = max(R in C_(t+1)) ≥ max(R in C_t) = R_selected(t)`

This guarantees a **nondecreasing selected stored FsfairX reward**, including when every new candidate is worse. It does not guarantee strict improvement, an increase in new-candidate mean reward, or an increase in another evaluator's score. An independent Qwen preference score can decrease because the answer that maximizes FsfairX is not necessarily the answer Qwen prefers.

I checked all 100 prompts: zero selected-reward violations for baseline→step0, step0→step1, or step1→step2. The baseline is the first initial sample; step0 is the best of those five; later stages use the cumulative candidate pool. Those definitions and the extraction are correct.

The paper's §4.2 specifies cumulative-cache selection. Its §6.1 curves measure average sampled-candidate RM reward; benchmark WR/LC results are reported separately. These are empirical results, not a theorem requiring an independent win rate to rise at every iteration. See the [paper](https://arxiv.org/html/2501.12895#S4.SS2), [training-curve section](https://arxiv.org/html/2501.12895#S6.SS1), and [published version](https://proceedings.mlr.press/v267/li25ac.html).

## What our experiment actually shows

| Stage | Selected RM mean | Qwen weighted WR (%) | LC (%) | Average answer length (characters) |
|---|---:|---:|---:|---:|
| baseline | -3.9737 | 9.14 | 16.29 | 828 |
| step0 / Best-of-5 | -2.3567 | 11.22 | 21.67 | 927 |
| step1 | -1.3607 | 10.09 | 16.02 | 1240 |
| step2 | -0.8038 | 8.27 | 10.51 | 1511 |
| Best-of-15 | -1.6083 | 14.02 | 24.53 | 1086 |

For the assignment's baseline→step1→step2 sequence, WR is non-monotonic and LC decreases. To isolate textual refinement from initial reward selection, the more informative trajectory is **step0→step1→step2**, where both WR point estimates decline. The +0.95 pp step1-minus-baseline difference combines Best-of-5 selection with refinement; it cannot be attributed entirely to textual feedback.

The mean reward of retained unique candidates rises too: -4.3244→-2.1534→-1.6642. This is not guaranteed by cumulative-best selection. A sensitivity check giving every prompt equal weight, rather than every retained candidate equal weight, also rises: **-4.3071→-2.3707→-1.8564**. All 100 prompts have retained candidates in each round. The proxy-reward improvement therefore is not solely a consequence of selecting the historical maximum or the specific candidate-weighting convention.

However, these averages describe retained candidates. Duplicate multiplicities and malformed discarded responses are unavailable. The 51-prompt complete-case analysis shows the same direction within that subset; it does **not** eliminate all survivorship bias, since membership depends on successful retention. `PROJECT_INFO.md`'s stronger claim that this rules out survivorship bias should be revised.

## Evaluation checks and statistical interpretation

I reconstructed **497 non-auto-tie annotations** from their saved first-token log probabilities and the exact seeded output-order flips. Every reconstructed preference matches its saved value; the other three annotations are valid identical-reference ties. This excludes a reversed-label or forgotten-order-flip explanation for the observed trend. The `m`/`M` labels account for at least 0.9999916 probability mass in every saved completion, so malformed first-token output is not an evident cause either. The parsing convention matches [AlpacaEval's parser](https://github.com/tatsu-lab/alpaca_eval/blob/main/src/alpaca_eval/completion_parsers.py).

Weighted WR is `100 × mean(preference - 1)`: a normalized logprob-based soft preference score against the fixed reference. It is not an integer count of prompts won, a direct step2-versus-step0 match, or a demonstrated calibrated probability of human preference. Identical answers across stages reuse the same preference. The valid protocol checks do not establish that this Qwen judge agrees with humans on this distribution.

Additional paired percentile bootstrap intervals, using the same 100 prompts, 10,000 resamples, seed 42:

| WR comparison | Difference (pp) | Paired 95% CI (pp) |
|---|---:|---|
| step1 − baseline | +0.95 | [-3.92, +6.06] |
| step1 − step0 | -1.13 | [-4.03, +1.17] |
| step2 − step1 | -1.82 | [-5.07, +1.41] |
| step2 − baseline | -0.87 | [-5.82, +4.20] |
| step2 − step0 | -2.95 | [-7.16, +1.03] |
| step2 − Best-of-15 | -5.74 | [-11.92, +0.007] |

All these intervals include zero. We can say the observed sequence is not monotonic and that the run fails to demonstrate a WR gain. We cannot claim this experiment establishes that population WR reliably decreases. Nor does a null-containing interval establish equivalence or absence of an effect. The intervals condition on the saved generations and judge responses; they do not include repeat-generation or repeat-judging variability. They are individual intervals, not a simultaneous confidence band proving or disproving monotonicity.

The tiny existing LC SEs are SEMs of fitted GLM predictions. They omit the uncertainty from fitting each stage's GLM and should not be used to claim statistically significant LC changes. Proper LC uncertainty would resample prompts and refit the model, with an explicitly chosen treatment of calibration data. The default fit also incorporates GPT-4-derived calibration, whose applicability to Qwen is unvalidated. Keep LC as a secondary descriptive result and use paired raw-WR uncertainty for the principal conclusion. The fitting and SE definitions are visible in [AlpacaEval's source](https://github.com/tatsu-lab/alpaca_eval/blob/main/src/alpaca_eval/metrics/glm_winrate.py).

The Qwen substitution makes this an adapted benchmark evaluation, rather than an exact reproduction of official GPT-4-judged AlpacaEval scores. Its absolute values cannot be compared directly with published benchmark scores.

## Explaining the absence of monotonic win-rate gains

**Proxy/evaluator mismatch is the explanation most directly supported by the measured divergence.** Refinement produces and selects higher-FsfairX-score answers, but these do not receive higher Qwen scores. In point estimates, Best-of-15 obtains a lower RM mean than step2 but a higher WR. This is consistent with overoptimization of the reward proxy, including selection for detail or style that does not improve task satisfaction. It remains a hypothesis about human-quality degradation: a different judge can disagree for its own reasons.

**Verbose or misdirected rewriting is a plausible mechanism.** Average length rises 63% from step0 to step2, while WR falls. Inspected losses include turning a short explanation of keeping a promise into a much longer answer, adding unnecessary detail to a simple capital-city question, and adding alternatives to a request for one CSS color. These examples illustrate plausible loss of focus; they do not prove that length itself causes lower scores. Two selected answers also contain evaluative commentary, showing imperfect separation of critique and final response.

**Small-model critique-following limits are plausible, but not isolated by this run.** The same 8B SFT policy must interpret comparisons, generate useful critique, and apply it. Refinement candidate deficits of 81/500 and 86/500 combine duplicate merging with possible missing-tag failures. Those causes cannot be separated without original replies. The paper discusses an 8B instruction-following failure in §7.4, on a different model/dataset/metric; it is contextual evidence rather than an exact reproduction of our result. See [§7.4](https://arxiv.org/html/2501.12895#S7.SS4).

**Finite-sample and evaluator uncertainty remain substantial.** A fixed 100-prompt slice, one generation run, and one unvalidated substitute judge cannot establish the causal mechanism. The strong GPT-4 reference also permits two weak answers both to score near zero, making small soft-score differences uninformative. In the earlier diagnostic, thresholding changes at 0.05 gave 5 wins / 10 losses / 85 ties for step2 versus step0; the unthresholded "55% improved" figure counts arbitrarily tiny changes and should not be read as a majority-quality improvement.

**Widespread tag leakage or output-cap truncation is not supported by the saved-output diagnostics.** No residual TextGrad tags were found in selected answers, step1/step2 maximum reconstructed lengths were 1160/1316 tokens, and the worst losses inspected did not show obvious cutoff endings. Exact historical truncation is still unidentifiable because finish reasons and raw optimizer responses were not saved.

## Reporting corrections and sensible follow-up

Describe this as a completed adapted replication that did not reproduce monotonic independent win-rate gains. Do not describe it as proven reward hacking, statistically established deterioration, or elimination of survivorship bias. Candidate selection is consistent with TPO; its monotonic proxy score is expected by construction.

For precise configuration documentation, temperature 0.7/top_p 0.95/seed 7 apply to initial and refinement candidate sampling. Critique and backward-gradient calls use the engine defaults: temperature 0.7, top_p 0.99, seed unset, and an 8192-token output cap. Seed 7 therefore does not seed every inference call. This matches the current official flow, but limits repeatability and should be stated.

If additional evidence is needed, first validate the judge with blinded answer inspection and both answer orders, then run prespecified extra generation seeds or a larger held-out prompt set while retaining D=2/N=5. Save raw candidate replies, extraction outcomes, and generation finish reasons. Direct step2-versus-step0 judgments would complement the existing fixed-reference metric. Any alternative judge, stronger critique model, cleaning procedure, or stopping rule should be reported as a separate experiment. Do not choose seeds or configurations because they produce a monotonic test curve, and do not use the final evaluator to select answers or iterations on those same test prompts.

Suggested report wording:

> On a fixed 100-prompt AlpacaEval-2 subset, TPO with an 8B SFT policy increased selected FsfairX reward but did not demonstrate monotonically improving independent Qwen-judged win rates. WR was 9.14%, 10.09%, and 8.27% for baseline, step1, and step2. Relative to the initial Best-of-5 output, step2 changed WR by -2.95 percentage points (paired bootstrap 95% CI [-7.16, 1.03]). This divergence is consistent with reward-proxy mismatch or ineffective refinement, but the sample size, substitute judge, and unavailable raw rejected refinements prevent a definitive causal attribution.
