# CV Tailoring Model Decision Sheet

_Last updated: 2026-03-10_

Purpose: a compact reference for choosing a model for JD-conditioned CV tailoring: bullets, summaries, skills sections, repair passes, scoring, and variant generation.

## Decision rule

- Use **standard API pricing** as the default comparison basis.
- Treat **Google free-tier rate limits as approximate**, because Google states that active limits depend on quota tier/account status and should be checked in **AI Studio**.
- For sensitive production CV data, note that Google states **Free tier content is used to improve their products**, while **Paid tier content is not**.

## Main comparison table

| Provider | Model | Free tier | Free-tier limitations / notes | Standard price input / output (USD per 1M tokens) | Best fit for this CV workflow | Main caveat |
|---|---|---:|---|---:|---|---|
| Google | Gemini 2.5 Flash-Lite | Yes | Officially: check AI Studio for active limits. Publicly documented 2.5-era guidance: **15 RPM, 250k TPM, 1,000 RPD**. Free tier data usage: **used to improve products**. | **$0.10 / $0.40** | Cheapest drafting, extraction, keyword gap analysis, simple rewrites | Lower ceiling for nuanced prioritization and polishing |
| Google | Gemini 2.5 Flash | Yes | Officially: check AI Studio. Publicly documented 2.5-era guidance: **10 RPM, 250k TPM, 250 RPD**. Free tier data usage: **used to improve products**. | **$0.30 / $2.50** | Best Google cost/quality balance for most section generation | Can still need repair pass for subtle relevance decisions |
| Google | Gemini 2.5 Pro | Yes | Officially: check AI Studio. Publicly documented 2.5-era guidance: **5 RPM, ~125k TPM noted in forum update, 100 RPD**. Free tier data usage: **used to improve products**. | **$1.25 / $10.00** for prompts <=200k; **$2.50 / $15.00** above 200k | Stronger reasoning for hard rewrites and prioritization | Much pricier than Flash; free tier is tight |
| Google | Gemini 3.1 Flash-Lite Preview | Yes | Officially: check AI Studio. Preview models may change and can have more restrictive limits. Free tier data usage: **used to improve products**. | **$0.25 / $1.50** | Cheap modern preview option for high-volume tasks | Preview risk; not ideal as sole production dependency |
| Google | Gemini 3 Flash Preview | Yes | Officially: check AI Studio. Preview models may change and can have more restrictive limits. Free tier data usage: **used to improve products**. | **$0.50 / $3.00** | Faster stronger preview choice than Flash-Lite | Preview risk |
| Google | Gemini 3.1 Pro Preview | No | Paid only. Preview model; may change before stable. | **$2.00 / $12.00** for prompts <=200k; **$4.00 / $18.00** above 200k | Strongest currently listed Google text option in this set | Preview + paid only |
| Google | Gemini 3 Pro Preview | No | **Deprecated / shut down on 2026-03-09** | N/A | Do not use | Unavailable |
| OpenAI | GPT-5-mini | No | No free tier equivalent for API comparison here | **$0.25 / $2.00** | Cheap extraction, tagging, JD keyword mapping, JSON stages | Weaker than GPT-5.4 for final wording quality |
| OpenAI | GPT-5.4 | No | No free tier equivalent for API comparison here | **$2.50 / $15.00** for prompts <272k; **$5.00 / $22.50** above 272k | Best overall baseline for high-quality CV sections | Costs materially more than Gemini Flash |
| OpenAI | GPT-5.4-pro | No | No free tier equivalent for API comparison here | **$30.00 / $180.00** for prompts <272k; **$60.00 / $270.00** above 272k | Escalation model for the hardest final-pass rewrites | Too expensive for default use |

## Sorted by cost (cheapest first)

Sort key below = **standard input price + standard output price** for the usual text workflow under the lower context threshold.

| Rank | Provider | Model | Standard price input / output (USD per 1M tokens) | Combined standard cost | Free tier | Recommendation summary |
|---|---:|---|---:|---:|---:|---|
| 1 | Google | Gemini 2.5 Flash-Lite | $0.10 / $0.40 | **$0.50** | Yes | Cheapest useful option for extraction and cheap drafting |
| 2 | Google | Gemini 3.1 Flash-Lite Preview | $0.25 / $1.50 | **$1.75** | Yes | Cheap preview option; better than ultra-cheap legacy-class drafts, but preview risk |
| 3 | OpenAI | GPT-5-mini | $0.25 / $2.00 | **$2.25** | No | Good cheap OpenAI helper model for structured substeps |
| 4 | Google | Gemini 2.5 Flash | $0.30 / $2.50 | **$2.80** | Yes | Best Google day-to-day default for CV generation |
| 5 | Google | Gemini 3 Flash Preview | $0.50 / $3.00 | **$3.50** | Yes | Strong preview option if you accept preview volatility |
| 6 | Google | Gemini 2.5 Pro | $1.25 / $10.00 | **$11.25** | Yes | Stronger Google reasoning, but much more expensive |
| 7 | Google | Gemini 3.1 Pro Preview | $2.00 / $12.00 | **$14.00** | No | Strong paid Google option, but preview |
| 8 | OpenAI | GPT-5.4 | $2.50 / $15.00 | **$17.50** | No | Best overall quality baseline for serious CV tailoring |
| 9 | OpenAI | GPT-5.4-pro | $30.00 / $180.00 | **$210.00** | No | Use only as premium escalation on hard final passes |

## Practical selection rules

### Lowest cost possible
Use **Gemini 2.5 Flash-Lite** for extraction and first drafts.

### Best Google balance
Use **Gemini 2.5 Flash** as the default section generator.

### Best overall quality baseline
Use **GPT-5.4** for final user-facing bullets, summaries, and polish.

### Premium escalation only
Use **GPT-5.4-pro** only when the default model fails repeatedly or the final pass is high-value enough to justify the cost.

### Avoid as sole dependency
Avoid making your whole pipeline depend on **preview** models.

## Recommended production architecture

1. **Stage A — extraction / alignment**
   - Cheap model: **Gemini 2.5 Flash-Lite** or **GPT-5-mini**
   - Output only structured JSON: required keywords, missing evidence, seniority hints, overclaim risk, irrelevant experience.

2. **Stage B — section drafting**
   - Default: **Gemini 2.5 Flash** or **GPT-5.4**

3. **Stage C — final polish**
   - Best quality: **GPT-5.4**

4. **Stage D — hard escalation**
   - Use **GPT-5.4-pro** only for exceptional cases

## Notes for scoring

Do not rely on a raw `0-100` score alone. Ask the model to also return:
- matched JD keywords,
- missing hard requirements,
- unsupported / risky claims,
- confidence,
- short rationale for relevance,
- and then the score.

## Source notes

### Google official
- Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
- Gemini API rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Gemini API models: https://ai.google.dev/gemini-api/docs/models
- Gemini deprecations: https://ai.google.dev/gemini-api/docs/deprecations

### OpenAI official
- OpenAI API pricing: https://developers.openai.com/api/docs/pricing/
- OpenAI API changelog (GPT-5.4 / GPT-5.4-pro release): https://developers.openai.com/api/docs/changelog/
- ChatGPT release notes (GPT-5.4 Thinking): https://help.openai.com/en/articles/6825453-chatgpt-release-notes

### Public Google forum note for approximate older free-tier 2.5 limits
- https://discuss.ai.google.dev/t/limits-of-free-tier-api-vs-ai-studio/94918

## Verification reminders before each launch

- Re-check **Google AI Studio** active rate limits for your account.
- Re-check whether any **preview** model has been promoted, deprecated, or shut down.
- Re-check whether prompt size crosses the provider’s higher pricing threshold.
- Re-check data policy if handling candidate-sensitive information.