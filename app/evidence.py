from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

from app.schemas import EvidenceBackedClaim, EmailDraft


RISKY_CLAIM_PHRASES = (
    "strong",
    "extensive",
    "extensively",
    "expert",
    "expertise",
    "deep knowledge",
    "end to end",
    "production",
    "production ready",
    "production minded",
    "designed",
    "architected",
    "owned",
    "led",
    "multiple",
    "well versed",
    "prompt engineering",
    "langchain",
    "vector store",
    "vector stores",
)


def normalize_for_evidence(value: str) -> str:
    """Normalize prose for conservative substring checks."""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[-_/]", " ", text)
    text = re.sub(r"[^\w+#.]+", " ", text)
    return " ".join(text.split())


def normalize_memory_records(
    memories: Iterable[dict[str, Any] | str],
) -> list[dict[str, str]]:
    """Return auditable memory records while preserving backwards compatibility."""
    records: list[dict[str, str]] = []
    for index, memory in enumerate(memories, start=1):
        if isinstance(memory, str):
            memory_id = f"memory_{index}"
            memory_type = "unknown"
            content = memory.strip()
        else:
            memory_id = str(memory.get("id", "")).strip() or f"memory_{index}"
            memory_type = str(memory.get("type", "unknown")).strip() or "unknown"
            content = str(memory.get("content", "")).strip()

        if not content:
            continue
        records.append({"id": memory_id, "type": memory_type, "content": content})

    if not records:
        raise ValueError("At least one non-empty profile memory is required.")
    return records


def validate_claim_evidence(
    claims: Iterable[EvidenceBackedClaim],
    memory_records: list[dict[str, str]],
    *,
    email_body: str | None = None,
) -> None:
    """Reject unknown evidence IDs and unsupported claim-strengthening language."""
    memory_by_id = {record["id"]: record["content"] for record in memory_records}
    normalized_body = normalize_for_evidence(email_body or "")

    for claim_index, claim in enumerate(claims, start=1):
        claim_text = claim.claim.strip()
        supporting_ids = list(dict.fromkeys(claim.supporting_memory_ids))
        unknown_ids = sorted(set(supporting_ids) - set(memory_by_id))
        if unknown_ids:
            raise ValueError(
                f"Claim {claim_index} references memories that were not retrieved: "
                f"{unknown_ids}."
            )
        if not supporting_ids:
            raise ValueError(f"Claim {claim_index} requires at least one memory ID.")

        normalized_claim = normalize_for_evidence(claim_text)
        if normalized_body and normalized_claim not in normalized_body:
            raise ValueError(
                f"Claim {claim_index} must appear verbatim in the generated email body."
            )

        supporting_text = normalize_for_evidence(
            " ".join(memory_by_id[memory_id] for memory_id in supporting_ids)
        )
        unsupported_phrases = [
            phrase
            for phrase in RISKY_CLAIM_PHRASES
            if normalize_for_evidence(phrase) in normalized_claim
            and normalize_for_evidence(phrase) not in supporting_text
        ]
        if unsupported_phrases:
            raise ValueError(
                f"Claim {claim_index} strengthens the evidence with unsupported wording: "
                f"{unsupported_phrases}."
            )


def validate_grounded_email_draft(
    email_draft: EmailDraft,
    memory_records: list[dict[str, str]],
) -> None:
    """Validate the machine-readable evidence ledger attached to an email draft."""
    if not email_draft.claim_evidence:
        raise ValueError("The email draft must include at least one evidence-backed claim.")
    validate_claim_evidence(
        email_draft.claim_evidence,
        memory_records,
        email_body=email_draft.body,
    )
