# Benchmark V2 Plan

## Objective

Benchmark V2 should test whether JobCopilot generalizes beyond short, strongly templated synthetic offers while preserving reproducibility, licensing safety and annotation traceability.

V2 is not intended to replace V1. V1 remains the frozen low-cost regression suite; V2 becomes the harder generalization and robustness suite.

## Target composition

Initial target: **100 offers**.

| Dimension | Target |
| --- | --- |
| Languages | 50 English, 50 French |
| Sources | Multiple licensed, redistributable or newly authored formats |
| Role families | At least 15 |
| Difficulty | 25 easy, 50 medium, 25 hard |
| Length | Short, medium and long offers |
| Formatting | Headings, prose, bullets, mixed layouts and table-like text |

Suggested role families include LLM applications, NLP, information retrieval, responsible AI, machine learning, data science, computer vision, MLOps, data engineering, analytics, cloud AI, AI research, applied statistics, optimization and AI product engineering.

## Challenge dimensions

Every case should carry explicit challenge metadata. The suite should include:

- missing company, location, contract or start date;
- contract-like words appearing only in a role title;
- obsolete header information corrected later in the text;
- multiple office locations with one final role location;
- remote, hybrid and travel requirements;
- required and preferred skills mixed in prose;
- technologies mentioned as context but not as requirements;
- abbreviations and expanded forms;
- bilingual or code-switched passages;
- negative requirements such as “experience with X is not required”;
- quoted customer projects that must not be attributed to the role;
- benefits and company capabilities that must not become candidate requirements;
- long distractor sections;
- duplicate and near-duplicate skills;
- contradictory statements requiring a documented precedence rule.

## Annotation policy

A written annotation manual must be frozen before final annotation.

### Evidence scope

For every extracted item, annotators should record:

- the normalized gold value;
- the exact supporting text span;
- the section or paragraph identifier;
- whether the value is explicit or resolved through an approved precedence rule;
- an optional ambiguity note.

### Domain-focus boundary

V2 must resolve the issue exposed by V1. Choose and document one of these policies:

1. **Global-evidence policy:** include domains supported anywhere in the offer, including the title;
2. **Dedicated-section policy:** include only labels stated in a designated domain or expertise section.

The recommended policy is global evidence with source spans, because it matches the meaning of `domain_focus` better. A separate `explicit_domain_section_labels` field can be added when dedicated-section fidelity matters.

### Required versus preferred skills

Annotators must not infer seniority, tools or requirements from general industry knowledge. A skill belongs to `required_skills` or `preferred_skills` only when the offer supplies evidence for that status.

## Annotation process

- Two independent annotators per case;
- blind annotation before comparison;
- adjudication for all disagreements;
- versioned annotation guidelines;
- inter-annotator agreement reported before adjudication;
- immutable case IDs and dataset hashes after release.

Agreement should be reported separately for scalar fields and set-valued fields rather than collapsed into a single score.

## Metrics

Retain protocol 1.2 outputs:

- normalized scalar accuracy;
- strict scalar accuracy;
- closed-label list precision, recall and F1;
- mission-summary exact F1 as a lexical diagnostic.

Add:

- evidence-span precision and recall;
- missing-field false-positive rate;
- contradiction-resolution accuracy;
- required-versus-preferred confusion matrix;
- exact-set accuracy per list field;
- performance by language, length, source format, difficulty and challenge type;
- latency and model-token cost per case;
- repeated-run stability across at least three runs.

A semantic mission-summary metric should be published only after validating it against human judgments. It must not silently replace the lexical diagnostic.

## Data splits and release discipline

- Freeze a public development split and a hidden or delayed test split;
- prohibit prompt tuning on the final test labels;
- publish dataset and prompt hashes for every result;
- record model identifier and run timestamp;
- keep V1 and V2 result tables separate;
- never merge results from different protocol versions without relabeling them.

## Acceptance criteria for a first V2 release

A release candidate is ready when:

1. all 100 cases pass schema and reference validation;
2. both languages and all difficulty levels meet their quotas;
3. every gold item has a supporting span;
4. double annotation and adjudication are complete;
5. no source has unresolved redistribution restrictions;
6. the evaluation script produces field-level and challenge-level slices;
7. at least one baseline model and one target model have been run three times;
8. limitations and known annotation ambiguities are documented.

## Recommended implementation sequence

1. Freeze the annotation guide and `domain_focus` policy;
2. author 20 pilot cases covering all challenge types;
3. double-annotate and audit the pilot;
4. update schemas and validators;
5. expand to 100 cases;
6. freeze dataset V2.0.0;
7. run baselines and stability experiments;
8. publish the full report with error taxonomy.

## Non-claims

Even a successful V2 result would not prove universal job-market accuracy. It would provide stronger evidence across the defined languages, formats, role families and challenge dimensions only.
