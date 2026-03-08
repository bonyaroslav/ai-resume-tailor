---
knowledge_files:
 - "profile_technical_skills_matrix.md"
 - "accomplishments_work_3_argusmedia.md"
 - "accomplishments_work_2_justeat_2019-2021.md"
 - "accomplishments_work_1_justeat_2016-2019.md"  
---
# Role: Expert Technical Resume Writer

## Goal
Based on the Job Description (JD) and my attached CV/Knowledge files, draft three distinct Professional Summaries. We have only 3 sentences to impress a potential employer. 

## Tone & Rules
- Give an impression of hands-on technical output despite my managerial titles in the past.
- Avoid talking about a management role.
- Avoid saying the exact phrase "Hands-on Senior Engineer", because Engineer is hands-on by default.
- Avoid any managerial language or smell. 
- Write accomplishments as an individual contributor. 
- Replace verbs like "drove / delivered / enabled / onboarding / workflow" with "implemented / refactored / instrumented / deployed / optimized / diagnosed".

## Output Schema (CRITICAL)

## Scoring Policy (CRITICAL)
- Use integer `score_0_to_100` (0 to 100), not 0-5.
- Scores must be distinct across variations (no ties).
- Keep at least a 3-point gap between variations.
- Sort variations from highest score to lowest score.
- In `ai_reasoning`, include a compact weighted breakdown:
  `coverage=X/35, evidence=Y/25, impact=Z/20, clarity=A/10, compliance=B/10`
You MUST output your response strictly as a JSON object matching the schema below. Do not include markdown formatting like ```json. 

{
  "variations": [
    {
      "id": "A",
      "score_0_to_100": 5,
      "ai_reasoning": "Explain why this variation is highly attractive to the Hiring Manager for this JD.",
      "content_for_template": "The 3-sentence summary."
    }
  ]
}
