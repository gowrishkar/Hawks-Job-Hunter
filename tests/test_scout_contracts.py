from hawks.scout import JobLead, dedupe_decisions, score_lead


def test_high_trust_ai_architect_role_is_shortlisted():
    lead = JobLead(
        title="AI Solutions Architect - Agentic Workflow Automation",
        company="Example AI",
        url="https://example.com/careers/ai-solutions-architect",
        location="Remote India / Global",
        source="official",
        summary="Own LLM agent orchestration, MCP tools, and enterprise workflow strategy.",
        tags=("AI Architect", "agent", "MCP"),
    )

    decision = score_lead(lead)

    assert decision.decision == "shortlist"
    assert decision.score >= 75
    assert "source trust: official" in decision.reasons
    assert any("target signal" in reason for reason in decision.reasons)


def test_unknown_junior_sales_role_is_rejected():
    lead = JobLead(
        title="Junior Sales Intern",
        company="Unknown",
        url="not-a-url",
        location="Local only",
        source="unknown",
        summary="Door to door sales role.",
    )

    decision = score_lead(lead)

    assert decision.decision == "reject"
    assert decision.score < 55
    assert decision.risks


def test_normalized_key_dedupes_company_title_location():
    lead = JobLead(
        title=" AI Product Manager ",
        company="Example AI",
        url="https://example.com/job",
        location=" Remote ",
        source="ats",
    )

    assert lead.normalized_key() == "example ai|ai product manager|remote"


def test_dedupe_decisions_keeps_best_evidence_for_same_role():
    board_mirror = JobLead(
        title="AI Product Manager",
        company="Example AI",
        url="https://board.example/jobs/123",
        location="Remote India",
        source="reputed_board",
        summary="AI product workflow role.",
    )
    official_page = JobLead(
        title="AI Product Manager",
        company="Example AI",
        url="https://example.com/careers/ai-product-manager",
        location="Remote India",
        source="official",
        summary="AI product workflow role with LLM agents.",
    )
    distinct_role = JobLead(
        title="AI Solutions Architect",
        company="Example AI",
        url="https://example.com/careers/ai-solutions-architect",
        location="Remote India",
        source="official",
        summary="Agentic workflow automation strategy.",
    )

    deduped = dedupe_decisions(
        [score_lead(board_mirror), score_lead(official_page), score_lead(distinct_role)]
    )

    assert len(deduped) == 2
    assert deduped[0].lead.url == "https://example.com/careers/ai-product-manager"
    assert deduped[1].lead.title == "AI Solutions Architect"
