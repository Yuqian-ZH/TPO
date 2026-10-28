# Protocol deviations and limits

- Frozen protocol `task1_frozen_v1` is a new experiment; historical results remain separate. New parameters are protocol choices, not claims that every value was required by the assignment or paper.
- Policy is Tulu-3-8B-SFT and RM is FsfairX; Qwen is exclusively the independent judge. Paper main AlpacaEval comparisons use a 70B policy.
- Same 100/805 AlpacaEval-2 slice (seed 42), original IDs/order and GPT-4 Turbo references; verified byte-identical to both histories. No resampling.
- vLLM context 16384. Response cap 2048; critique/gradient cap 8192. Temperature .7 and top_p .95 for candidates, .99 for critique/gradient.
- Every policy request now has SHA-256-derived seed, including previously unseeded critique/gradient calls. Request shape n=5/n=15 is preserved; seed is per request. Persistent eight-worker pool. Results are not promised bit-identical across scheduling/machines.
- Transport journals replace the official blanket five-attempt retry decorator and SDK retry with at most three total attempts (2s, 8s delays), only transient transport/429/500/502/503/504 errors. No answer-quality or tag-failure retries. First successful responses and RM calls are checkpointed; resumes check complete request and protocol/source/data hashes.
- Official TPO functions, optimizer parameter/value/context construction, response-tag parsing, RM and cumulative cache rules remain unchanged. Compatibility source patch from existing checkout is preserved separately, including TextGrad setup readme fix and max_tokens argument repair. The effective token caps are explicit.
- Existing pyairports 2.1.1 repair is pinned to NICTA commit 9699eae8c6b03c97239018dea92e01daa8594936. No global environment modification was made during the run.
- Qwen `qwen3.8-max` replaces official GPT-4 Turbo; exact weighted prompt and soft logprob parser retained. Temperature 1, max_tokens 1, logprobs true, top_logprobs 5, thinking false, output-order seed 0. No immutable dated judge snapshot is exposed. Fresh formal cache, separate from historical and preflight caches.
- LC retains GPT-4-derived calibration and is unvalidated/descriptive under Qwen. LC uncertainty conditions on fitted GLM and excludes fitting uncertainty.
- Best-of-15 matches requested response candidates (15), not critiques/gradients, total tokens or FLOPs. Missing tags/duplicates are reported without resampling.
- GPU 2/3 were verified free on the host. Sandboxed driver access initially failed; host checks resolved this. Preflight replay initially used an isolated default tokenizer cache path; fixed it to the pinned local snapshot, then verified six prompt/mode replays without API or RM calls. This was a path fix, not a scoring-driven change.
- Existing model snapshots were available; offline mode was used. New machines must download/authenticate for model weights first. Separate tpo/aeval environment inventories are saved. A clean-machine installation has not been performed.
- Any endpoint rejection will be preserved in the request-attempt journals; no silent parameter substitution is permitted.

- Output publication uses the unchanged frozen exporter in `export_staging/` and copies only stage files into the main directory. This avoids adding a terminal newline to the frozen reference input. `scripts/export_saved.sh` was added as an output-path guard after freeze, before judging; inference, data content/order, analysis rules and judge settings were unchanged. Its hash and purpose are recorded in run_config.json.
