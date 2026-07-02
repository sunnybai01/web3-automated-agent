def propose_options(verified_facts: dict) -> dict:
    title = verified_facts.get("title", "Opportunity")
    amount = verified_facts.get("amount", "unknown reward")
    deadline = verified_facts.get("deadline", "unknown deadline")

    assumptions = [
        f"Prize budget context: {amount}",
        f"Submission date context: {deadline}",
    ]

    return {
        "options": [
            {
                "tier": "light",
                "summary": f"Build a lean MVP for {title} with core demo only.",
                "assumptions": assumptions,
            },
            {
                "tier": "standard",
                "summary": f"Ship a production-like prototype for {title} with observable metrics.",
                "assumptions": assumptions,
            },
            {
                "tier": "advanced",
                "summary": f"Implement end-to-end architecture for {title} with resilience and scale tests.",
                "assumptions": assumptions,
            },
        ]
    }