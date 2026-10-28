# Process diagnostics

| Iteration | Stored unique | Prompts with candidates | Candidate weighted mean RM | Equal prompt mean RM |
|---|---|---|---|---|
| init | 495 | 100 | -4.2334 | -4.2193 |
| iter1 | 406 | 100 | -2.0048 | -2.2530 |
| iter2 | 407 | 100 | -1.5347 | -1.7832 |

| Stage | Iteration | Requests | Returned | Parsed | Missing tags | Duplicate merges | Empty | Raw finish=length | Raw metadata flags |
|---|---|---|---|---|---|---|---|---|---|
| initial | -1 | 100 | 500 | 500 | 0 | 5 | 0 | 3 | 0 |
| critique | 0 | 100 | 100 | None | 0 | None | 0 | 0 | 100 |
| critique | 1 | 100 | 100 | None | 0 | None | 0 | 0 | 100 |
| gradient | 0 | 100 | 100 | None | 0 | None | 0 | 0 | 85 |
| gradient | 1 | 100 | 100 | None | 0 | None | 0 | 0 | 88 |
| refinement | 0 | 100 | 500 | 497 | 3 | 91 | 0 | 6 | 6 |
| refinement | 1 | 100 | 500 | 498 | 2 | 91 | 0 | 6 | 22 |
| bon15 | -1 | 100 | 1500 | 1500 | 0 | 39 | 0 | 11 | 0 |

| Stage | Selected with response provenance | Selected raw finish=length | Selected metadata flags |
|---|---|---|---|
| baseline | 100 | 0 | 0 |
| step0 | 100 | 1 | 0 |
| step1 | 100 | 1 | 2 |
| step2 | 100 | 1 | 3 |
| bon15 | 100 | 0 | 0 |

Raw finish_reason=length is a length cap flag and does not prove semantically incomplete text.

Metadata phrase counts are screening heuristics, not proven failures.

Candidate duplicate merging uses the official within-iteration cache key; identical text in different rounds remains separate.

Generation phase wall time excludes RM loading; policy request sums overlap across workers; RM sums include queue wait.
