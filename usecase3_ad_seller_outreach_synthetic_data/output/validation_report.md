# ML + NLP + GenAI Pipeline -- Validation Report

Run started: 2026-11-26 12:51:17
Elapsed: 192.9s
Model: gpt-5.2

## Schema compliance

Every GenAI call is validated against its Pydantic schema by the OpenAI SDK at response time -- a response that doesn't match the schema raises and is retried (see structured_call()), so every result below already passed validation.

- Accounts processed: 3
- GenAI calls per account: 3 (stage 6 ads analysis, stage 8 market mapping, stage 9 email copy)
- Total structured calls made: 9 (expected 3 accounts x 3 = 9)

## Token usage & cost

```
{
  "num_calls": 9,
  "total_input_tokens": 38964,
  "total_output_tokens": 12301,
  "cost_by_model_usd": {
    "gpt-5.2": null
  }
}
```

## Per-account result

- **DE-INS-001**: constraint = rank-constrained, confidence = 0.86, campaign findings = 3, recommendation cards = 4, already working = 3, opportunity = +610,980 impressions
- **US-RET-001**: constraint = budget-constrained, confidence = 0.86, campaign findings = 5, recommendation cards = 5, already working = 3, opportunity = +315,330 impressions
- **UK-TRV-001**: constraint = rank-constrained, confidence = 0.84, campaign findings = 2, recommendation cards = 4, already working = 3, opportunity = +30,240 impressions