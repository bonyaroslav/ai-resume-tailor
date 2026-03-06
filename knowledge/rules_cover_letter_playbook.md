
0. Goal
   Produce a tailored, short, high-signal cover letter for a specific job description. Also produce a reusable “Company Insight Brief” and “Excitement Angles” that drive credible “why them” lines.

1. Hard rules (MUST)

* Never fabricate facts, numbers, employers, titles, or company specifics.
* If a fact is unknown: use [PLACEHOLDER] and list what’s needed to replace it.
* The cover letter must complement the CV, not reprint it.
* Prefer outcomes and evidence over traits and adjectives.
* No negativity, blame, drama, or personal oversharing.
* No salary discussion unless explicitly required by the application.
* Respect user style constraints (example: no em dash) as strict.

2. Inputs
   Required if available:

* JD text (or link) + company name + role title + location/remote.
* 3–6 user proof points (achievement bullets) with context and any metrics.
  Optional but helpful:
* Links: company site, product page, engineering blog, GitHub, press, reviews.
* Logistics: timezone, work authorization, start window.

If proof points are missing:

* Draft with [PLACEHOLDER] metrics and ask for 2–3 missing details at the end.

3. Output schema (always return in this exact order)
   A) Company Insight Brief (structured)
   B) Excitement Angles (8–12 items, grouped)
   C) Tailored Cover Letter (final)
   D) Hooks (5 options)
   E) “Why them” lines (8 options)
   F) Proof bullets (8–10, reusable for CV)
   G) Placeholder list (only if placeholders exist)

4. Company Insight Brief (fields)
   Fill with verified facts where possible; if not possible, use “From JD” or “Inference (low confidence).”
   Fields:

* Product: what it is in one sentence
* Customers: who uses it
* Value: what outcome it improves
* Domain constraints: compliance/regulation, latency, reliability, security, integrations
* Tech signals: stack/tools/patterns explicitly mentioned
* Delivery signals: ownership, on-call, autonomy, collaboration
* Culture signals: pace, quality bar, remote style (only if sourced)
* Likely pain points (3): what the role probably fixes
* Differentiators (3): why this company vs others (facts)
* Risks/unknowns (3): what’s unclear and should be validated
* Sources used: list of links or “JD only”

5. Excitement Angles (method)
   Generate 8–12 angles in groups:

* Product impact (2–3)
* Technical challenge (2–3)
* Ownership/craft (2–3)
* Team/culture/growth (2–3)
  For each angle, output:
* Angle title
* Proof anchor (the fact that triggered it)
* 1-line “why them” sentence the user can put into a letter

6. JD-to-evidence mapping (internal logic)
   Extract the JD top 3 priorities:

* Priority #1 (must-have)
* Priority #2
* Priority #3
  Map each to a user proof point:
* JD priority -> user proof -> metric/outcome -> 1 sentence for the letter
  If a priority has no proof: write a “transfer statement” (how the user’s adjacent experience applies) without claiming they have already done it.

7. Cover letter defaults + decision rules
   Default length: 250–350 words. 1 page max.
   If the user is pasting into a short portal textbox: produce a micro-letter 120–180 words instead.
   Format decision:

* If the JD is high-volume/startup/modern: allow 2–3 bullets in paragraph 2.
* If the company is formal/enterprise/regulated: prefer paragraph style (no bullets).

8. Cover letter structure (default)
   Paragraph 1: Hook (2–3 lines)

* IC identity + domain + strongest proof (metric/outcome)
* Specific “why them” fact (from Insight Brief)
  Paragraph 2: Evidence
* 2–4 proof points mapped to JD priorities
* Each point uses: Context -> Action -> Result -> (optional tech constraint)
  Paragraph 3: Why them + close
* One sentence connecting strengths to their next 90 days goals
* Optional logistics (timezone/authorization/start)
* Calm call to action

9. Bullet writing rules (proof bullets)
   Each bullet must include at least:

* verb + what + outcome
  Preferred:
* metric, scale, or operational indicator (latency, error rate, uptime, MTTR, cost, throughput, adoption)

10. Forbidden patterns (DO NOT)

* Generic opener with no proof (“excited to apply…” as first line).
* CV retelling chronology.
* Keyword dumping (listing many technologies without outcomes).
* Claims you cannot defend in interview.
* “Passion” paragraphs without evidence.
* Over-claiming leadership for a pure IC role.

11. Placeholder protocol

* Use [PLACEHOLDER] inline.
* At the end, list exactly what’s needed to finalize, in 3–6 short bullets.
* If placeholders exceed 4: shorten the letter and ask for missing data.

12. QA checklist (before final output)

* First 2–3 lines contain: role + company + best proof point
* Each evidence point ties to a JD priority
* At least one specific company fact is included (or clearly marked “From JD”)
* No fluff/cliches, no contradictions, no forbidden patterns
* Length and style constraints respected

END FILE