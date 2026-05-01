from app.memory import retrieve_profile_context
from app.services.llm import (
    analyze_job_offer,
    generate_match_insight,
    generate_application_email_draft,
)
from app.services.applications_store import (
    create_application_record,
    add_application_record,
    load_application_records,
)


def main() -> None:
    job_text = """
    Andra Learning is hiring a Stage / Alternance — IA Agentic & Automatisation in Paris.

    You will work directly with the CTO and AI Lead to build AI agents that automate and enrich
    the learning experience of B2B sales teams.

    Responsibilities:
    - Design and implement agentic workflows
    - Integrate LLMs such as Claude and GPT via APIs
    - Build RAG pipelines
    - Develop bots and connectors for Microsoft Teams, CRM, calendars, and search tools
    - Set up monitoring and evaluation for AI outputs

    Profile:
    - Strong interest in generative AI and agentic systems
    - Python and/or TypeScript
    - Experience with LLM APIs
    - Bonus: RAG, prompt engineering, agent frameworks, open source
    """

    print("\n=== STEP 1: Analyze job offer ===")
    job_analysis = analyze_job_offer(job_text)
    print(job_analysis.model_dump())

    query = (
        f"{job_analysis.role}. "
        f"Required skills: {', '.join(job_analysis.required_skills)}. "
        f"Tools and stack: {', '.join(job_analysis.tools_and_stack)}. "
        f"Domain focus: {', '.join(job_analysis.domain_focus)}."
    )

    print("\n=== STEP 2: Retrieve relevant profile memories ===")
    docs = retrieve_profile_context(query, k=5)
    retrieved_memories = [doc.page_content for doc in docs]

    for i, memory in enumerate(retrieved_memories, start=1):
        print(f"[{i}] {memory}")

    print("\n=== STEP 3: Generate match insight ===")
    match = generate_match_insight(
        job_analysis=job_analysis,
        retrieved_profile_memories=retrieved_memories,
    )
    print(match.model_dump())

    print("\n=== STEP 4: Generate application email draft ===")
    email_draft = generate_application_email_draft(
        job_analysis=job_analysis,
        match_insight=match,
    )
    print(email_draft.model_dump())

    print("\n=== EMAIL SUBJECT ===")
    print(email_draft.subject)

    print("\n=== EMAIL BODY ===")
    print(email_draft.body)

    print("\n=== STEP 5: Save application record ===")
    record = create_application_record(
        company=job_analysis.company,
        role=job_analysis.role,
        email_subject=email_draft.subject,
        email_body=email_draft.body,
        status="drafted",
        source="manual",
        notes="Generated from JobCopilot MVP pipeline.",
    )
    add_application_record(record)
    print(record.model_dump())

    print("\n=== STEP 6: Show stored application records ===")
    records = load_application_records()
    print(f"Total saved applications: {len(records)}")
    for i, item in enumerate(records, start=1):
        print(f"[{i}] {item.company} | {item.role} | {item.status} | {item.created_at}")


if __name__ == "__main__":
    main()