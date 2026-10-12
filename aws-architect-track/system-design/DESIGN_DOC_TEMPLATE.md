# <System name> — Design

## 1. Requirements
- Functional:
- Non-functional (with numbers):
- Out of scope:

## 2. Estimates
Show the arithmetic, not only the result.
- Requests/s (average, peak):
- Storage per year:
- Bandwidth in / out:
- Hot data set size (what must fit in memory):

## 3. API
Endpoints or messages, with the idempotency story for every write.

## 4. Data model
Tables or collections, partition/sort keys, and the access pattern each key serves.
Name the key most likely to go hot.

## 5. Architecture
Diagram plus one paragraph per component: why it is there and what it costs.

## 6. Key flows
Step-by-step for the two or three most important requests, including the failure path.

## 7. Failure modes
| What fails | How it is detected | What the user sees | Recovery |
|---|---|---|---|

## 8. Cost
Monthly estimate at the stated scale; every line traced to a pricing page.

## 9. Decisions
Links to `adr/NNNN-title.md`. Each ADR: context, options, decision, consequences.

## 10. What would change at 10x
