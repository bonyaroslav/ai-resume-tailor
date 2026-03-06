<a name="readme-top"></a>

<div align="center">
  <h2>🚀 AI Resume Tailor</h2>
  <p><b>A Local, Graph-Based State Machine for ATS-Optimized CV Generation</b></p>

  <p align="center">
    <a href="https://github.com/your_username/ai-resume-tailor/issues">Report Bug</a>
    ·
    <a href="https://github.com/your_username/ai-resume-tailor/issues">Request Feature</a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.10+-blue.svg?style=for-the-badge&logo=python" alt="Python">
    <img src="https://img.shields.io/badge/Architecture-State_Machine-brightgreen.svg?style=for-the-badge" alt="Architecture">
    <img src="https://img.shields.io/badge/AI-Provider_Agnostic-orange.svg?style=for-the-badge" alt="LLM">
    <img src="https://img.shields.io/badge/Privacy-100%25_Local-purple.svg?style=for-the-badge&logo=lock" alt="Privacy">
  </p>
</div>

---

## 📖 The Problem & The Solution

**The Problem:** Over 70% of resumes are automatically rejected by Applicant Tracking Systems (ATS) because they lack the specific semantic vocabulary of the target Job Description. Yet, manually rewriting a CV for every application is a massive time sink, and standard ChatGPT outputs sound generic and hallucinate facts.

**The Solution:** `AI Resume Tailor` is a platform-agnostic, local Python CLI tool. It acts as a **Directed Graph State Machine** that mathematically cross-references your real experience against a target Job Description. It conditionally routes tasks, generates ATS-compliant CV sections concurrently, and pauses for a human-in-the-loop review before assembling a final `.docx`.

---

## ✨ Key Features

* **🎯 ATS Semantic Alignment:** Rewrites bullet points to match the exact vocabulary and technical phrasing expected by the target company's ATS, without inventing fake experience.
* **🔄 Graph-Based Agentic Workflow:** Utilizes a cyclic workflow (Fan-out/Fan-in) allowing for infinite "regeneration loops" on specific sections without losing API context.
* **🛑 Human-in-the-Loop (HITL):** Built-in checkpointing pauses execution, presenting a CLI menu for A/B testing and manual refinement of generated text.
* **🔌 Provider-Agnostic LLM Layer:** Built with dependency injection. Easily swap between Google Gemini, OpenAI GPT-4, or Anthropic Claude by simply changing an environment variable.
* **🔒 Zero-Data-Leak Architecture:** Runs 100% locally. Your personal data is isolated via YAML Frontmatter injection and protected by strict `.gitignore` rules.

---

## 🧠 System Architecture

Instead of relying on heavy third-party agent frameworks, this core engine is built as a native, lightweight **Directed Graph State Machine**. This ensures high maintainability, strict typing (via Pydantic), and rapid execution.

```mermaid
graph TD
    A[Start: CLI Input JD] --> B(Node 1: Triage)
    B -->|Cross-reference JD vs Base Skills| C{Is it a fit?}
    C -->|No-Go| D[Terminate Pipeline]
    C -->|Go| E(Node 2: Concurrent Fan-Out)
    
    E --> F[Generate Summary]
    E --> G[Generate Exp 1]
    E --> H[Generate Exp 2]
    
    F --> I(Node 3: Human-in-the-Loop Checkpoint)
    G --> I
    H --> I
    
    I -->|User Rejects a Draft| J[Capture Feedback String]
    J -. Backward Edge .-> E
    
    I -->|User Approves All| K(Node 4: Assembly)
    K --> L[Inject {{Placeholders}}]
    L --> M[Export CV.docx]

```

### 📐 Architecture Decision Records (ADRs)

1. **Why a Custom State Machine over LangChain?** While LangChain/LangGraph are excellent, they often introduce unnecessary abstraction overhead for strictly scoped CLI tools. By building a native Python state passing mechanism, the execution path remains highly deterministic, deeply understandable, and significantly faster to test.
2. **Context Isolation via Frontmatter:**
To completely eliminate LLM hallucinations, prompts do not read the entire "knowledge base" blindly. Markdown prompts utilize YAML frontmatter to surgically request *only* the specific text files they need (e.g., `Prompt 3` only requests `Argus_Media_Achievements.md`).


---

## 🗺️ Roadmap (V2 Enhancements)

V1 focuses on delivering a deterministic, lightweight State Machine. Once the core pipeline is locked, the following architectural upgrades are planned:

* **Multi-Agent Evaluator (LLM-as-a-Judge):** Introducing a "Critic Node" that acts as a ruthless ATS Recruiter. It will automatically score the generated drafts against the JD *before* presenting them to the human. If a draft scores poorly, the graph will autonomously loop back to the Writer node for a rewrite.
* **100% Air-Gapped Local Execution:** Adding a `LocalProvider` interface via **Ollama / vLLM**. This will allow the pipeline to run entirely offline using local models (e.g., Llama 3), ensuring absolute data sovereignty without a single byte leaving the user's machine.
* **Local Semantic RAG:** Transitioning from static YAML Frontmatter to a local Vector Database (e.g., ChromaDB). The system will use Cosine Similarity to dynamically inject only the most mathematically relevant achievements from the user's career history into the AI's context window.

---

## 🚀 Getting Started

### Prerequisites

* Python 3.10+
* An API Key (Google Gemini, OpenAI, etc.)

### Installation

1. Clone the repo
```sh
git clone [https://github.com/your_username/ai-resume-tailor.git](https://github.com/your_username/ai-resume-tailor.git)

```


2. Set up a virtual environment
```sh
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

```


3. Install dependencies
```sh
pip install -r requirements.txt

```


4. Set your environment variables
```env
# .env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_api_key_here

```



---

## 💻 Usage

**1. Start a New Tailoring Session:**

```sh
python main.py new --jd-path ./inputs/stripe_jd.txt --company "Stripe"

```

**2. Resume a Paused Review Session (from JSON Checkpoint):**

```sh
python main.py resume --state-path ./runs/Stripe-01/state_checkpoint.json

```

*(Optional: Insert a `.gif` here showing your CLI menu in action. Hiring managers love seeing the tool actually working in a terminal).*

---

## 🛡️ Privacy & Security

This application is designed with a **Zero-Trust approach to the Cloud**.
All personal receipts, skills, and base CV data live exclusively in the `knowledge/` directory, which is strictly `.gitignore`'d. Run outputs are saved to a local `runs/` directory. No data is stored in vector databases or external servers outside of the ephemeral LLM API call.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.