# JobCopilot Benchmark Annotation Guide

## Scope

Version 1 evaluates three separate capabilities:

1. structured extraction from job offers;
2. retrieval of relevant candidate memories;
3. factual grounding of candidate claims in generated emails.

The tasks must remain separate. A strong extraction score does not imply good retrieval, and a good retrieval score does not imply that the final email is grounded.

## 1. Job-offer extraction

Annotate only information supported by the offer text.

### Scalar fields

- `company`: employer or organization explicitly responsible for the opening;
- `role`: the target role, not a neighboring role mentioned as context;
- `location`: final operative location when the text contains a correction;
- `contract_type`: the most specific supported form of employment;
- `start_date`: the supported date or expression, otherwise `Unknown`.

Use `Unknown` when the information is absent. Do not infer a permanent contract from words such as “join our team.”

### List fields

- `required_skills`: mandatory qualifications or abilities;
- `preferred_skills`: optional, bonus or desirable qualifications;
- `tools_and_stack`: named technologies, frameworks, platforms or methods;
- `domain_focus`: the main technical or research themes.

Keep items short and atomic. Do not convert responsibilities into candidate skills unless the offer explicitly presents them as requirements.

## 2. Profile-memory retrieval

Each query has:

- `relevant_ids`: memories that should appear in the retrieved set;
- `relevance_by_id`: graded judgments where 3 means highly relevant, 2 relevant and 1 marginally relevant.

Judge whether a memory helps support a candidate-to-role comparison. General identity information should not outrank direct project or experience evidence for a technical query.

Reported metrics:

- Recall@1, Recall@3 and Recall@5;
- mean reciprocal rank;
- NDCG@1, NDCG@3 and NDCG@5.

## 3. Candidate-claim grounding

Review factual claims about the candidate, not generic statements about the company or motivation.

Split compound sentences when their clauses require different evidence.

Allowed labels:

- `supported`: the claim is directly supported by one or more retrieved memories;
- `unsupported`: no retrieved memory supports the claim, or the claim contradicts the evidence;
- `ambiguous`: the evidence is related but too weak, broad or incomplete to verify the claim.

For every supported or ambiguous claim, record `supporting_memory_ids`. Unsupported claims must use an empty list.

### Examples

- “The candidate built a LangGraph workflow.” → supported by `project_1`.
- “The candidate deployed Kubernetes systems in production.” → unsupported when no memory states this.
- “The candidate is an expert in cloud operations.” → ambiguous when the evidence only lists Docker or FastAPI exposure.

The main grounding metric is:

```text
unsupported claim rate = unsupported claims / all reviewed candidate claims
```

Ambiguous claims are reported separately rather than silently counted as supported.

## Review process

Version 1 is single-annotator curated. A stronger future release should use two independent reviewers, adjudicate disagreements and report agreement before publishing performance claims.
