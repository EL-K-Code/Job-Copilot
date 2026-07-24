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

_CLAIM_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "by",
    "candidate",
    "for",
    "from",
    "had",
    "has",
    "have",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "with",
}


_ALIAS_PATTERNS = (
    (r"\bretrieval augmented generation\b", "rag"),
    (r"\bnatural language processing\b", "nlp"),
    (r"\blarge language models?\b", "llm"),
    (r"\bmachine learning\b", "ml"),
    (r"\bapplication programming interfaces?\b", "api"),
)


def normalize_for_evidence(value: str) -> str:
    """Normalize prose for conservative evidence checks."""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[-_/]", " ", text)
    text = re.sub(r"[^\w+#.]+", " ", text)
    for pattern, replacement in _ALIAS_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return " ".join(text.split())


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = f" {normalize_for_evidence(text)} "
    normalized_phrase = f" {normalize_for_evidence(phrase)} "
    return normalized_phrase in normalized_text


def _light_stem(token: str) -> str:
    """Apply a small deterministic stemmer for common English inflections."""
    for suffix in ("ingly", "edly", "ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            stem = token[: -len(suffix)]
            if len(stem) >= 3 and stem[-1:] == stem[-2:-1]:
                stem = stem[:-1]
            return stem
    return token


def _anchor_tokens(value: str) -> set[str]:
    """Return content-bearing tokens used to link a claim to an email sentence."""
    tokens = normalize_for_evidence(value).replace(".", " ").split()
    return {
        _light_stem(token)
        for token in tokens
        if token not in _CLAIM_STOPWORDS and len(token) > 2
    }


def _body_segments(email_body: str) -> list[str]:
    """Split an email into sentence-like units for local claim matching."""
    return [
        segment.strip()
        for segment in re.split(r"(?<=[.!?])\s+|\n+", email_body)
        if segment.strip()
    ]


def _claim_is_represented_in_body(claim_text: str, email_body: str) -> bool:
    """
    Check whether one sentence in the body carries the material lexical anchors of
    a claim. This permits harmless wording changes while rejecting disconnected
    evidence ledgers.
    """
    normalized_claim = normalize_for_evidence(claim_text)
    normalized_body = normalize_for_evidence(email_body)
    if normalized_claim and normalized_claim in normalized_body:
        return True

    claim_tokens = _anchor_tokens(claim_text)
    if not claim_tokens:
        return False

    minimum_matches = 1 if len(claim_tokens) == 1 else 2
    if len(claim_tokens) >= 5:
        minimum_matches = 3

    for segment in _body_segments(email_body):
        segment_tokens = _anchor_tokens(segment)
        overlap = len(claim_tokens & segment_tokens)
        coverage = overlap / len(claim_tokens)
        if overlap >= minimum_matches and coverage >= 0.60:
            return True
    return False


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

        if email_body and not _claim_is_represented_in_body(claim_text, email_body):
            raise ValueError(
                f"Claim {claim_index} is not sufficiently represented in a single "
                "sentence of the generated email body."
            )

        supporting_text = " ".join(
            memory_by_id[memory_id] for memory_id in supporting_ids
        )
        unsupported_phrases = [
            phrase
            for phrase in RISKY_CLAIM_PHRASES
            if _contains_phrase(claim_text, phrase)
            and not _contains_phrase(supporting_text, phrase)
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
