# AetherBench report

Rows: 116 | tasks x modes: 100

## First attempt, by tier and mode

| tier | mode | n | check@1 | run_correct@1 |
|------|------|---|---------|---------------|
| T1 | full | 10 | 80% (8/10) | 80% (8/10) |
| T1 | nl | 10 | 90% (9/10) | 90% (9/10) |
| T2 | full | 10 | 100% (10/10) | 100% (10/10) |
| T2 | nl | 10 | 100% (10/10) | 100% (10/10) |
| T3 | full | 10 | 100% (10/10) | 100% (10/10) |
| T3 | nl | 10 | 100% (10/10) | 90% (9/10) |
| T4 | full | 10 | 100% (10/10) | 90% (9/10) |
| T4 | nl | 10 | 100% (10/10) | 100% (10/10) |
| T5 | full | 10 | 100% (10/10) | 100% (10/10) |
| T5 | nl | 10 | 90% (9/10) | 90% (9/10) |

## Fix-loop ablation (failed first attempts only)

| arm | tasks entered | fixed | fix rate | mean iterations to green |
|-----|---------------|-------|----------|--------------------------|
| prose | 6 | 5 | 83% (5/6) | 1.00 |
| structured | 6 | 6 | 100% (6/6) | 1.17 |

## First-attempt failures

| task | mode | stage | diagnostic |
|------|------|-------|------------|
| t1_04_factorial | full | check | E0201 |
| t1_08_power | full | check | E0201 |
| t1_08_power | nl | check | E0201 |
| t3_05_fs_roundtrip | nl | run | WRONG_OUTPUT |
| t4_10_template | full | run | E9003 |
| t5_06_config | nl | check | E0201 |
