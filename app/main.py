from app.graph import jobcopilot_graph


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
    """

    result = jobcopilot_graph.invoke(
        {"job_text": job_text},
        config={"configurable": {"thread_id": "local-test"}},
    )

    print(result)


if __name__ == "__main__":
    main()