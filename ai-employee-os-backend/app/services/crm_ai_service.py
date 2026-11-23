from app.schemas.crm_ai import CustomerAIRequest, CustomerAIResponse


def generate_customer_insights(
    customer: CustomerAIRequest,
) -> CustomerAIResponse:
    stage = customer.stage

    actions = {
        "lead": (
            "Contact the customer to understand their requirements.",
            "high",
        ),
        "qualified": (
            "Schedule a discussion and prepare a suitable proposal.",
            "high",
        ),
        "proposal": (
            "Follow up on the proposal and answer any questions.",
            "high",
        ),
        "negotiation": (
            "Discuss outstanding concerns and confirm the next steps.",
            "high",
        ),
        "won": (
            "Thank the customer and coordinate project delivery.",
            "medium",
        ),
        "lost": (
            "Record the reason for losing the opportunity.",
            "low",
        ),
    }

    suggested_action, priority = actions[stage]

    summary = (
        f"{customer.name}"
        f"{' from ' + customer.organization if customer.organization else ''}"
        f" is currently in the {stage} stage."
    )

    if customer.notes:
        summary += f" Customer notes: {customer.notes.strip()}"

    return CustomerAIResponse(
        summary=summary,
        suggested_action=suggested_action,
        priority=priority,
        generated_by="rules",
    )