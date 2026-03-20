# playbook: Engineering Manager Cover Letter

This version is designed for AI generation of a **short, tailored, human-sounding EM cover letter**.

## 0. Goal

Produce a tailored, short, high-signal cover letter for a specific **Engineering Manager** role.

The letter should:

* sound human, calm, and direct
* be about **3 sentences**
* complement the CV instead of repeating it
* show **leadership plus technical credibility**
* include one specific, credible “why them” point
* stay easy for recruiters and hiring managers to scan

Default target length:

* **90–140 words**
* about **3 sentences**
* one short paragraph, or three very short paragraphs if needed

---

## 1. Hard rules

* Never fabricate facts, metrics, employers, titles, team size, budget, scope, or company specifics
* If a fact is unknown, use **[PLACEHOLDER]**
* Do not repeat the CV in prose form
* Prefer evidence over adjectives
* No negativity, blame, drama, or personal oversharing
* No salary discussion unless explicitly requested
* Respect user style constraints as strict
* **No em dashes**
* Avoid sounding like a template or corporate press release

---

## 2. Inputs

Use if available:

* JD text or link
* company name
* role title
* location / remote setup
* 2–4 proof points from the user
* team scope, delivery scope, architecture scope, or metrics
* company/product/blog/press links if provided

Helpful but optional:

* work authorization
* timezone
* start window

If proof is missing:

* draft conservatively with **[PLACEHOLDER]**
* list what is needed at the end

---

## 3. Internal logic

Extract the JD’s top 3 priorities:

* leadership / people management
* delivery / execution / cross-functional ownership
* technical credibility / architecture / platform / reliability

Map each priority to real user evidence.

If direct proof is missing:

* use a **transfer statement**
* do not imply the user has already done it if they have not

The letter should usually use:

* **1 company-specific fact**
* **2 proof points**
* **1 clear EM fit statement**

Do not output the internal mapping unless the user asks for it.

---

## 4. What an EM letter must signal

The letter should make the reader feel:

* this person can lead engineers
* this person can deliver through others
* this person still understands technical depth
* this person can work across product, platform, and stakeholders
* this person has evidence, not just management language

Strong EM signals include:

* team leadership
* hiring, mentoring, or coaching
* roadmap / delivery ownership
* cross-team coordination
* architecture direction
* modernization
* reliability or incident leadership
* platform or systems thinking
* measurable operational or business outcomes

Hands-on credibility should appear as:

* technical judgment
* architecture reviews
* incident handling
* deep dives
* quality standards
* modernization leadership
* selective hands-on involvement if true

Do not let the letter sound like a pure IC application. Do not let it sound like a non-technical manager either. This balance matches current EM cover-letter advice to show both managerial and technical strengths with specific examples. ([indeed.com][2])

---

## 5. Default structure

### Sentence 1: Role + company + EM identity + why them

Say:

* the exact role
* the company
* your EM identity
* one specific reason this company or role is relevant

Pattern:

* “I’m applying for the Engineering Manager role at [Company] because [specific product / platform / mission / technical challenge], and my background leading [teams / domain / platform] aligns closely with what you need.”

### Sentence 2: Best evidence

Use 1–2 proof points tied to the JD.

Pattern:

* “In recent roles, I’ve led [team/scope] while driving [delivery / modernization / reliability / platform work], including [specific example + metric or visible outcome].”

### Sentence 3: Fit + close

Connect strengths to their likely needs and close simply.

Pattern:

* “I’d bring a mix of people leadership, execution, and technical judgment to help [Company] [next-step outcome], and I’d welcome the chance to discuss the role.”

---

## 6. “Why them” rule

The letter must contain **one specific reason** for this company.

Good sources:

* product
* engineering challenge
* platform scale
* domain complexity
* reliability / security context
* company stage
* delivery model
* something clearly stated in the JD

Weak:

* “your innovative company”
* “your strong reputation”
* “your exciting mission”

Good:

* a real product context
* a real scaling challenge
* a real domain constraint
* a real organizational need from the JD

The letter should be tailored and company-specific, which is consistent with current university and job-search guidance. ([Career Development Center][1])

---

## 7. Evidence rules

Use proof that is strongest for EM hiring:

Best:

* led a team of X
* delivered a program across X teams
* improved reliability / performance / delivery speed by X
* owned modernization or architectural change
* reduced incidents / cost / lead time
* improved hiring, onboarding, retention, or team effectiveness
* delivered in a regulated / high-scale / high-availability environment

Good:

* drove cross-functional delivery
* improved engineering standards
* led platform or service evolution
* handled high-stakes incidents or migrations

Weak:

* long tech-stack list
* vague leadership claims
* generic “collaborated with stakeholders”
* chronology of previous jobs

---

## 8. Forbidden patterns

Do not use:

* “I am excited to apply” as the opening
* resume retelling
* long tool or stack dumps
* vague adjectives like:

  * dynamic
  * passionate
  * results-driven
  * visionary
* claims that cannot be defended in interview
* IC-heavy phrasing that centers only on coding
* generic management phrasing with no technical signal
* em dashes
* overlong closings

---

## 9. Output schema

Return in this order:

### A) Final cover letter

Only the final EM cover letter, ready to use.

### B) Placeholder list

Only if placeholders exist.

Optional only if the user asks:

* alternate version
* stricter ATS version
* warmer / more human version
* “why them” options
* JD-to-evidence mapping

Do **not** output research scaffolding by default.

---

## 10. Placeholder protocol

* Use **[PLACEHOLDER]** inline
* If placeholders are used, list exactly what is needed to finalize
* Keep the list short, usually **2–4 items**
* If more than 4 placeholders are needed, shorten the letter further

---

## 11. QA checklist

Before final output, check:

* First sentence includes role, company, and a specific reason for this company
* The letter sounds like an **Engineering Manager**, not an IC
* At least one sentence shows both leadership and technical credibility
* At least one proof point is concrete
* The letter complements the CV rather than repeating it
* The tone is human, direct, and concise
* No clichés
* No em dashes
* No unsupported claims
* About 3 sentences total

---

## 12. Final principle

This letter is not a biography and not a second resume.

It is a short note that says:

* I understand your context
* I have led in similar conditions
* I still have technical judgment
* here is the proof
* this is why I am relevant to you now


[1]: https://career.oregonstate.edu/cover-letters "Cover Letters | Career Development Center | Student Affairs | Oregon State University"
[2]: https://www.indeed.com/career-advice/cover-letter-samples/engineering-manager "Engineering Manager Cover Letter Example and Template  | Indeed.com"
[3]: https://www.jobscan.co/cover-letter-templates "18 Free Cover Letter Templates That Will Actually Get You Interviews"
