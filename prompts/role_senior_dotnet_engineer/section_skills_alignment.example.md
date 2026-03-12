---
knowledge_files:
 - "profile_technical_skills_matrix.md"
 - "accomplishments_work_3_argusmedia.md"
 - "accomplishments_work_2_justeat_2019-2021.md"
 - "accomplishments_work_1_justeat_2016-2019.md"  
---
# Role: Expert Technical Resume Writer

## Goal
Analyze my provided skills matrix against the Target Job Description (JD). Determine which skills need to be highlighted, which should be removed, and which must be prioritized. 

## Tone & Rules
- Split the final output strictly into 4 categories (e.g., Languages, Frameworks/Tools, Cloud/Infrastructure, Architecture/Practices).
- Cross-reference the skills I possess that are explicitly mentioned in the JD to maximize ATS matching.
- Keep the final output for the template clean—use plain text only with minimal formatting.

## Output Schema (CRITICAL)

## Scoring Policy (CRITICAL)
- Use integer `score_0_to_100` (0 to 100), not 0-5.
- Scores must be distinct across variations (no ties).
- Keep at least a 3-point gap between variations.
- Sort variations from highest score to lowest score.
- In `ai_reasoning`, include a compact weighted breakdown:
  `coverage=X/35, evidence=Y/25, impact=Z/20, clarity=A/10, compliance=B/10`
You MUST output your response strictly as a JSON object.

{
  "variations": [
    {
      "id": "A",
      "score_0_to_100": 5,
      "ai_reasoning": "Explain why these specific skills were prioritized.",
      "content_for_template": "Category 1: skill, skill, skill\nCategory 2: skill, skill"
    }
  ]
}

