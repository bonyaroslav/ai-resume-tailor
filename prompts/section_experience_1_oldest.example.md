---
knowledge_files:
  - "profile_technical_skills_matrix.md"
  - "accomplishments_company_3_latest.md"
---
# Role: Expert Technical Resume Writer

## Goal
Generate 2 variations of four high-impact resume bullet points for my latest Senior Engineering role. Use the attached accomplishments and the JD. Try to make it concise.

## Tone & Rules
- Avoid any managerial language or smell. Write accomplishments as an individual contributor.
- Replace verbs like "drove / delivered / enabled / onboarding / workflow" with "implemented / refactored / instrumented / deployed / optimized".
- Attach at least one concrete engineering artifact (e.g., API contract, consumer, schema, index template, dashboard, CI/CD release) to every bullet point.

## Specific Role Clarifications & Exclusions
- Do NOT mention [Project A] as I was not the primary technical contributor.
- Focus heavily on [Technology B] and [Technology C] as they align best with the target JD.

## Output Schema (CRITICAL)
You MUST output your response strictly as a JSON object matching the schema below. Do not include markdown formatting like ```json. 

{
  "variations": [
    {
      "id": "A",
      "score_0_to_5": 5,
      "ai_reasoning": "Explain the value highlighted and list keywords used.",
      "content_for_template": "Bullet 1\nBullet 2\nBullet 3\nBullet 4"
    }
  ]
}