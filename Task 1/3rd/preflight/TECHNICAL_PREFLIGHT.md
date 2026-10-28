# Technical preflight

PASS: fixed first three prompts, official Tulu policy and FsfairX RM; TPO D=2/N=5 and BoN15. All five stage exports contain three aligned nonempty outputs. 24 successful generation requests explicitly carry deterministic per-prompt/stage/iteration seeds. The vLLM server logs show these seeds in received SamplingParams (see server_log_excerpt.txt); the SDK did not discard them. Candidate n=5/n=15 request shape is retained.

PASS: six prompt/mode checkpoints were reconstructed using the unchanged official algorithm and saved policy/RM journals with fresh generation hooks disabled. Changed-prompt reuse was rejected before API access. Evidence: replay_verification.json.

PASS: three Qwen weighted annotations returned valid finite non-all-tie preferences. Thinking disabled; populated top logprobs. Formal judge cache is separate from preflight and historical caches. Judge reports alias qwen3.8-max; no dated snapshot exposed.

Preflight path correction: initial replay check could not find the tokenizer after cache isolation; changed only the replay check to use its pinned absolute snapshot. No prompt was regenerated and no score-informed sampling change was made. The original failed log is retained as replay.log.

Full raw policy/RM/judge requests and responses are journaled in this preflight directory; no credentials are logged. Formal generation must start only after freeze.json exists.
