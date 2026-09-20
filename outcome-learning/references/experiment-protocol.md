# Experiment Protocol Template

> When to read: while executing the outcome-learning skill.

```text
OUTCOME_HYPOTHESIS
goal: <goal id>
hypothesis: <population> in <scenario> will <behavior> because <mechanism>
falsified_by: <observation that would refute it>
baseline:
  - source: <data/observation + date>
  - value: <baseline metric or "missing">
metrics:
  primary:
    - name: <metric>
      definition: <numerator/denominator or query>
      source: <where measured>
      window: <duration>
  guardrails:
    - name: <metric that must not regress>
      threshold: <value>
interpretation_rules:
  - support: <condition>
  - insufficient: <condition>
  - refuted: <condition>
experiment:
  design: <observation | small rollout | A/B>
  population: <who is included/excluded>
  duration: <time or sample size>
  stop_conditions: <when to stop early>
  privacy:
    - data_minimized: <what is collected and why>
    - consent/authorization: <basis>
    - retention: <how long>
results:
  - observed: <value + date>
    conclusion: support | insufficient | refuted
    limitations: <confounds, missing data>
recommendation: continue | revise | pause (owner decides)
```

Rules:

- A missing baseline is recorded as a gap, never filled with intuition.
- Guardrail regressions override a primary-metric win: report both.
- Insufficient evidence is a valid, honest result; do not round it up to
  support because the delivery is complete.
- The recommendation is advice; the owner records the actual decision.
