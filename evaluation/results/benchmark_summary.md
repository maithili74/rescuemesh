# RescueMesh Randomized Benchmark

Benchmark seed: `42`

## Planning Benchmark

| Metric | Result |
|---|---:|
| Randomized planning scenarios | 50 |
| Valid safe plans | 46 |
| Valid safe plan rate | 92.0% |
| Fully rescued | 46 (92.0%) |
| Partially rescued | 0 (0.0%) |
| Safely rejected | 4 (8.0%) |
| Weighted food rescued | 89.62% |
| Average scenario rescue rate | 92.0% |
| Unsafe plans | 0 |
| Capacity violations | 0 |
| Driver double-booking violations | 0 |
| Driver shift violations | 0 |
| Pickup deadline violations | 0 |
| Average planning latency | 6422.78 ms |
| P95 planning latency | 6631.29 ms |

## Disruption Benchmark

| Metric | Result |
|---|---:|
| Disruption scenarios executed | 10 |
| Autonomous recoveries | 10 |
| Autonomous recovery rate | 100.0% |
| Human escalations | 0 |
| Human escalation rate | 0.0% |
| Unsafe autonomous recoveries | 0 |
| Average disruption response latency | 791.05 ms |
| P95 disruption response latency | 1396.7 ms |

## Safety Interpretation

A scenario is counted as an unsafe plan if the
returned deterministic rescue plan violates one or
more independently checked invariants, including
driver capacity, pantry capacity, driver shift,
pickup deadline, double booking, or food quantity
accounting.

A disruption counts as an autonomous recovery only
when RescueMesh produces a full safe in-transit
replacement. Partial in-transit recovery requiring
a decision is counted as a human escalation rather
than autonomous success.
