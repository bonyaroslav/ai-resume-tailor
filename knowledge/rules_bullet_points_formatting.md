## Module: Canonical Software Engineer CV Bullet Points

ATS-friendly + hiring-manager readable + universal for IC engineers

### Purpose

Generate strong, truthful work-experience bullet points for software engineers that:

* parse cleanly in ATS
* match the target job description naturally
* show concrete technical contribution
* read fast for human reviewers
* remain easy to defend in interviews

This module is for general software engineers and should stay universal. Do not assume any specific career transition story.

---

## 0) Definition of done

For each role:

* Recent or highly relevant roles: 4–8 bullets
* Older or less relevant roles: 2–4 bullets
* Usually keep each bullet to 1–2 lines
* Every bullet must be interviewable and factually defensible
* Prioritize recent, relevant, high-impact accomplishments first

If the user asks for a short version:

* Use 3–5 bullets maximum for the role

---

## 1) Core rule

A strong bullet describes:

* what you changed
* how you changed it
* why it mattered

Default pattern:

* Action + technical context + result

Good bullet shapes:

* Built [component/system] using [relevant tech], reducing [problem] by [metric/result]
* Optimized [service/query/pipeline], improving [latency/reliability/cost] from [before] to [after]
* Automated [process], cutting [manual effort/failures/time] by [result]
* Hardened [area], reducing [risk/errors/incidents] and improving [outcome]

Do not force one punctuation style. Use whatever phrasing is most natural and easiest to scan.

---

## 2) What each bullet should contain

Aim for 3–5 of these signals per bullet:

* strong action verb
* concrete technical object
* relevant method or technology
* measurable result or visible effect
* scale, complexity, or constraint

Examples of strong technical objects:

* API
* microservice
* background worker
* event pipeline
* database query
* deployment pipeline
* observability stack
* integration
* cache
* data model
* migration

Examples of strong action verbs:

* built
* designed
* implemented
* optimized
* automated
* migrated
* debugged
* hardened
* instrumented
* refactored
* stabilized
* simplified

---

## 3) Results that count

Prefer results that show engineering impact:

Reliability

* incident reduction
* lower error rate
* better uptime
* lower MTTR
* fewer failed jobs or retries

Performance

* lower p95/p99 latency
* faster query time
* better throughput
* lower queue lag
* lower CPU or memory pressure

Delivery and developer experience

* faster CI/CD
* shorter lead time
* fewer escaped defects
* reduced build or test time
* safer releases

Cost and efficiency

* reduced cloud spend
* lower database load
* fewer support hours
* less manual work

Security and risk

* remediated vulnerabilities
* hardened auth or secrets handling
* improved audit readiness
* reduced exposure to failure modes

Truth rule:

* Use exact numbers when known
* If the number is approximate, mark it honestly: ~, approx., over, more than, from X to Y, hours to minutes
* Never invent precision

This outcome-first, accomplishment-focused style is consistent with current tech resume guidance. ([techinterviewhandbook.org][1])

---

## 4) ATS tailoring workflow

### Step A: extract target signals from the job description

Create two buckets:

A-rank

* top repeated must-have skills
* core responsibilities
* main technologies
* domain-critical terms

B-rank

* secondary tools
* adjacent practices
* supporting domain terms

### Step B: map achievements to those signals

For each candidate bullet, check:

* direct A-rank match
* secondary B-rank match
* clear outcome
* seniority or complexity signal
* technical relevance

### Step C: curate, do not stuff

Draft more bullets than needed, then keep the strongest mix:

* highest relevance to the JD
* strongest proof of impact
* enough variety across systems and results
* minimal repetition of the same keyword or story

ATS guidance supports mirroring the job description truthfully, using the exact job title when appropriate, and surfacing relevant skills clearly without keyword stuffing. ([Jobscan][3])

---

## 5) Ordering rules

Within each role, order bullets roughly like this:

1. strongest JD-aligned impact
2. second strongest impact
3. architecture, scale, or design contribution
4. reliability or performance work
5. automation or developer productivity
6. collaboration or mentoring only if it adds technical value

Put the most relevant proof first. Recruiters and hiring managers skim.

---

## 6) Formatting guardrails

Use resume formatting that ATS can parse cleanly:

* reverse-chronological work history
* standard section headings
* simple bullet formatting
* standard fonts
* no tables or decorative layouts inside experience
* one idea per bullet
* consistent tense and punctuation

For resume-level alignment:

* use the exact target job title near the top if truthful
* keep relevant keywords in the skills section and reinforce them in experience bullets
* prefer familiar section names

These are directly aligned with current ATS-oriented guidance for software engineer resumes. ([techinterviewhandbook.org][1])

---

## 7) Anti-generic rules

Do not write bullets that sound interchangeable.

Avoid:

* vague responsibility bullets with no result
* buzzwords without proof
* repeated sentence rhythm across every bullet
* inflated claims you cannot explain
* filler phrases like “dynamic,” “innovative,” “cross-functional,” “exceeding stakeholder expectations,” unless they are tied to concrete evidence

Use AI only as a drafting aid. Final bullets must be customized, specific, and fact-checked against real work. Recruiters have explicitly complained about generic, buzzword-heavy, inconsistent AI-written resumes. ([Business Insider][2])

---

## 8) Preferred evidence hierarchy inside bullets

Best

* metric with concrete result
* before and after comparison
* scale plus outcome
* technical change plus business effect

Good

* clear technical contribution with visible effect
* reduced pain, improved reliability, enabled delivery

Weak

* responsibility-only statement
* stack-only statement
* generic teamwork statement
* buzzword claim with no proof

Examples:

* Strong: Optimized SQL queries and indexing for a high-traffic API, reducing p95 response time from 780 ms to 240 ms
* Strong: Automated deployment validation checks, cutting failed releases by 40%
* Weak: Responsible for backend performance improvements
* Weak: Worked in an agile team on cloud solutions

---

## 9) Per-bullet quality check

Before finalizing a bullet, ask:

1. Does it name a real system, component, or process?
2. Does it show my technical contribution clearly?
3. Does it include a result or concrete effect?
4. Does it match the target role naturally?
5. Could I explain it confidently in an interview?
6. Is it more specific than a generic AI-generated bullet?
7. Is it different enough from the other bullets?

If the answer to 2, 3, or 5 is no, rewrite it.

---

## 10) Output protocol for bullet generation

When generating bullets for a role:

1. Read the JD and extract A-rank and B-rank terms
2. Draft a larger candidate pool
3. Curate to the strongest final set
4. Keep bullets concise and non-repetitive
5. Prefer conservative, defensible wording over exaggerated wording
6. If requested, provide:

   * one safer version
   * one slightly stronger version
   * one alternative rewrite for the top bullet

---

## 11) Source notes

Use these sources as supporting evidence, not as rigid law:

* Tech Interview Handbook: strong for ATS-safe tech resume structure, work experience format, accomplishments, and keyword optimization ([techinterviewhandbook.org][1])
* Jobscan: strong for JD keyword alignment, exact job title matching, and accomplishment-focused work experience ([Jobscan][4])
* Toptal Tech Resume guidance: strong for reverse-chronological format, ATS readability, and emphasizing results over responsibilities ([toptal.com][5])
* Business Insider: useful as a cautionary signal about generic AI-written phrasing, not as a primary resume standard ([Business Insider][2])

---

[1]: https://www.techinterviewhandbook.org/resume/ "Practical guide to writing FAANG-ready software engineer resumes | Tech Interview Handbook"
[2]: https://www.businessinsider.com/recruiters-job-search-resume-interview-ai-2025-7 "Recruiters to Job Searchers: Don't Act Like AI, Even If Use It - Business Insider"
[3]: https://www.jobscan.co/blog/20-ats-friendly-resume-templates/ "ATS-Friendly Resume in 2026 | How to Write Your Resume"
[4]: https://www.jobscan.co/blog/writing-your-resume-work-experience/ "How to Describe Work Experience on Your Resume (+Examples)"
[5]: https://www.toptal.com/techresume/career-advice/the-perfect-tech-resume-in-2025-key-trends-ats-keywords-and-formatting-tips "The Perfect Tech Resume in 2025: Key Trends, ATS Keywords, and Formatting Tips"
