# Confidence-aware model routing

Phase 4 makes LLM selection an explicit, auditable engineering policy. The goal is not to maximize model size; it is to use the smallest configured tier that satisfies the task contract and escalate only when deterministic signals justify it.

## Routing policy

```text
ProfileExtraction ─────────────── economy
JobAnalysis (normal offer) ───── economy
JobAnalysis (long offer) ─────── standard
EmailEvidenceSelection ───────── economy
MatchInsight ─────────────────── standard
AgentChat ────────────────────── standard

quality gate failure
        │
        └─────────────────────── strong repair
```

`LLM_ROUTING_MODE=single` is the backward-compatible control condition: all operations start at the standard tier.

## Why this is confidence-aware without trusting model confidence

JobCopilot does **not** ask a model to report a confidence score and then trust that score. Escalation is driven by deterministic system signals:

- `MatchInsight`: claim/evidence validation fails because a factual claim cannot be tied to retrieved memory IDs;
- `EmailEvidenceSelection`: selected IDs fail the deterministic memory-selection contract;
- long job offers can bypass the economy tier using a deterministic character threshold, avoiding another classifier call.

A strong-tier retry therefore means "the current result failed a contract", not "the model said it felt uncertain".

## Provider/model tiers

Each provider can configure three logical tiers independently:

- `*_ECONOMY_MODEL`
- `*_MODEL` (standard)
- `*_STRONG_MODEL`

If two tiers point to the same model they are deduplicated, so routing does not create duplicate provider calls merely because logical tiers overlap.

Provider fallback remains separate from model-tier routing. For example, the system may try an economy OpenAI model, then stronger OpenAI candidates on transport/provider failure, then an available Anthropic fallback according to the configured provider chain.

## Cost observability

Provider prices are intentionally **not hard-coded** in JobCopilot. Pricing changes over time and silent stale prices would make cost comparisons misleading.

The deployment can provide:

```text
LLM_PRICING_VERSION=<dated or reviewed label>
LLM_PRICING_JSON=<provider:model rate catalog>
```

Each catalog entry contains:

```json
{
  "input_per_million_usd": 0.0,
  "output_per_million_usd": 0.0
}
```

The zero values above illustrate the schema only; they are not provider price claims.

When the provider exposes token metadata and the used model exists in the configured catalog, JobCopilot reports:

- estimated cost per successful call;
- aggregate estimated cost for the current application analysis;
- pricing coverage;
- cost by operation;
- the pricing-version label used for the estimate.

When rates or token usage are unavailable, the UI says cost is unavailable rather than inventing a number.

## Privacy boundary

Routing telemetry may contain:

- provider;
- model;
- operation;
- economy / standard / strong tier;
- deterministic routing reason;
- whether the attempt is a quality escalation;
- latency;
- token counts when available;
- error class.

It does not retain prompts, job text, CV/profile facts, generated application text, API keys or OAuth tokens.

## Evaluation protocol

The implementation and unit tests establish routing behavior, but they do **not** prove that adaptive routing is better than a single large/standard model.

A valid empirical comparison must run the same versioned synthetic cases under both `adaptive` and `single` modes and compare at least:

- task-contract / grounding pass rate;
- extraction or task quality on labeled cases;
- latency;
- token usage;
- estimated cost under one explicit pricing catalog;
- escalation rate;
- provider fallback rate.

Quality, latency and cost claims must only be added to the README or CV after that benchmark is actually run and reviewed.
