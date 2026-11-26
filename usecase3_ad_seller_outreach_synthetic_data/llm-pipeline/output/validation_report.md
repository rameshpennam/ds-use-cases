# ML + NLP + GenAI Pipeline -- Validation Report

Run started: 2026-11-26 09:04:58
Elapsed: 136.9s
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
  "total_input_tokens": 22719,
  "total_output_tokens": 6915,
  "cost_by_model_usd": {
    "gpt-5.2": null
  }
}
```

## Per-account result

- **DE-INS-001**: constraint = rank-constrained, confidence = 0.88, campaign findings = 3
- **US-RET-001**: constraint = budget-constrained, confidence = 0.9, campaign findings = 5
- **UK-TRV-001**: constraint = rank-constrained, confidence = 0.8, campaign findings = 2