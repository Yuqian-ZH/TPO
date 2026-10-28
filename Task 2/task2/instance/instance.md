# Task 2 CVRP instance (`task2_cvrp_v1`)

Machine-readable spec: `cvrp_instance.json`. Figure: `instance.png`. Oracle report: `oracle_report.json`.

## Specification

- 1 depot (node 0), 8 customers (nodes 1-8), 2 identical vehicles, capacity Q = 100 each, no time windows.
- Objective: Minimize total travel distance (sum of both route lengths). Each vehicle leaves the depot exactly once and returns to it, so both vehicles are used; every customer is served by exactly one vehicle; the demand served by a vehicle may not exceed its capacity.
- Distance: c_ij = floor(euclidean(i, j) + 0.5): symmetric integers, so objective values are integers.
- Total demand 189 > Q, so both vehicles are needed.

| Node | x | y | Demand |
|---|---|---|---|
| 0 (depot) | 50 | 50 | 0 |
| 1 | 56 | 46 | 52 |
| 2 | 14 | 26 | 24 |
| 3 | 66 | 29 | 49 |
| 4 | 35 | 11 | 12 |
| 5 | 49 | 13 | 14 |
| 6 | 97 | 46 | 16 |
| 7 | 6 | 8 | 11 |
| 8 | 42 | 93 | 11 |

Distance matrix:

| | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| **0** | 0 | 7 | 43 | 26 | 42 | 37 | 47 | 61 | 44 |
| **1** | 7 | 0 | 47 | 20 | 41 | 34 | 41 | 63 | 49 |
| **2** | 43 | 47 | 0 | 52 | 26 | 37 | 85 | 20 | 73 |
| **3** | 26 | 20 | 52 | 0 | 36 | 23 | 35 | 64 | 68 |
| **4** | 42 | 41 | 26 | 36 | 0 | 14 | 71 | 29 | 82 |
| **5** | 37 | 34 | 37 | 23 | 14 | 0 | 58 | 43 | 80 |
| **6** | 47 | 41 | 85 | 35 | 71 | 58 | 0 | 99 | 72 |
| **7** | 61 | 63 | 20 | 64 | 29 | 43 | 99 | 0 | 92 |
| **8** | 44 | 49 | 73 | 68 | 82 | 80 | 72 | 92 | 0 |

Triangle inequality violations after rounding: 0.

## Optimal solution

Total distance **351**, unique up to vehicle relabeling and route reversal (second best 356).

| Vehicle | Route | Length | Load | Stops |
|---|---|---|---|---|
| 1 | 0 → 1 → 4 → 7 → 2 → 0 | 140 | 99 | 4 |
| 2 | 0 → 5 → 3 → 6 → 8 → 0 | 211 | 90 | 4 |

Arrival mileage A[i] (distance driven from the depot until customer i, in the canonical direction): A[1]=7, A[2]=97, A[3]=60, A[4]=48, A[5]=37, A[6]=95, A[7]=77, A[8]=167.

Conventions: In the reference solution the route containing customer 1 is vehicle 1. Each route runs so that its first customer has a smaller index than its last.

## Design goals (checked by brute force)

| Goal | Requirement | Result | OK |
|---|---|---|---|
| D1 | Unique optimum; second best strictly worse | optimum 351, second best 356 (gap 5) | True |
| D2 | Some pair of customers exceeds Q together | 1+3: 101 | True |
| D3 | Dropping capacity changes the optimal grouping | uncapacitated optimum 294 with grouping [1] / [2, 7, 4, 5, 3, 6, 8] | True |
| D4 | Both loads ≥ 0.8Q | [99, 90] | True |
| D5 | Route length ratio ≥ 1.2 | [140, 211] → 1.5071 | True |

## Gurobi cross-check

Gurobi 13.0.3 (size-limited license): objective 351, canonical routes equal to the oracle: True. Model size 185 variables (160 binary), 176 constraints (limit 2000).

## Generation

`instance/generate_instance.py` with seed 20261022: candidate #874 is the first meeting D1-D5 (873 rejected: 872 by the demand-only D2 pre-check, 1 by the oracle {'D5': 1}). Coordinates are uniform integers in [0, 100] (depot fixed at (50, 50)); demands are uniform integers in [10, 55], redrawn until the total is in [170, 190].

## Capacity structure

14 customer groupings are capacity-feasible. Decisions of the optimal solution whose prohibition is infeasible (capacity-forced): SEP(1,3). Every other decision is preferred by the objective (prohibiting it stays feasible but costs more).
