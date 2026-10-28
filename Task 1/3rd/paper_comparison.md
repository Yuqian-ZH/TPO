# Comparison with the paper

The published ICML 2025 paper, Table 1, evaluates a 70B SFT policy with FsfairX reward model and D2-N5: WR 16.8 → 40.5%, LC 27.8 → 33.0%. These are background, not directly comparable targets for this 8B-policy, 100-prompt, Qwen-judged run. The table’s FsfairX 8B model is the reward model, not an 8B policy. There is no directly corresponding 8B-policy AlpacaEval WR table.

Section 7.4 and Figure 7 discuss an 8B-Instruct policy on HH-RLHF and instruction following; this is another dataset and a different policy. A nonmonotonic result here does not demonstrate that the paper or code is wrong, and a monotonic point estimate would not alone establish comprehensive reproduction. RM/judge divergence is not proof of reward hacking or a specific causal explanation.

Verified against the preserved published PDF/text (`tpo_icml2025.pdf`, Table 1 and §7.4). Publication: [Li et al., Test-Time Preference Optimization, ICML 2025](https://proceedings.mlr.press/v267/li25ac.html).
