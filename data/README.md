# Profile memory files

## Active public demo profile

`profile_memories.atomic.json` is the active fictional public profile used by JobCopilot and by generated-email grounding reviews.

Each record is intentionally narrow and contains:

- `id`: stable evidence identifier;
- `type`: identity, education, experience, project, skill or preference;
- `topic`: the single main fact or technology represented by the memory;
- `group_id`: the broader evidence family;
- `content`: one conservative candidate fact that can be reused directly in a grounded email.

The atomic format prevents a match on one technology from importing unrelated technologies into an application email. For example, Python and PyTorch are separate memories instead of one broad stack sentence containing Python, SQL, PyTorch, FastAPI, Git and Docker.

## Frozen V1 profile

`profile_memories.example.json` is retained for the published V1 retrieval and static-grounding benchmarks. It must not be silently replaced because the frozen V1 annotations reference its original memory IDs.

New product and grounding experiments should use `profile_memories.atomic.json`. Historical V1 benchmark results must continue to use `profile_memories.example.json` and be reported separately.

## Private local profile

A private deployment may point `PROFILE_MEMORIES_FILE` to another JSON file with the same required fields. Personal profile files, CV contents and locally generated FAISS indexes must not be committed to the public repository.
