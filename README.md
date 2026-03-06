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
    <img src="https://img.shields.io/badge/AI-Gemini_V1-orange.svg?style=for-the-badge" alt="LLM">
    <img src="https://img.shields.io/badge/Privacy-100%25_Local-purple.svg?style=for-the-badge&logo=lock" alt="Privacy">
  </p>
</div>

---

## 📖 The Problem & The Solution

**The Problem:** Over 70% of resumes are automatically rejected by Applicant Tracking Systems (ATS) because they lack the specific semantic vocabulary of the target Job Description. Yet, manually rewriting a CV for every application is a massive time sink, and standard ChatGPT outputs sound generic and hallucinate facts.

**The Solution:** `AI Resume Tailor` is a local Python CLI tool built as a small **Directed Graph State Machine**. It routes a job description through triage, concurrent section generation, human review, and final `.docx` assembly without relying on heavy agent frameworks.

---

## ✨ Key Features

* **🎯 ATS Semantic Alignment:** Rewrites bullet points to match the exact vocabulary and technical phrasing expected by the target company's ATS, without inventing fake experience.
* **🔄 Graph-Based Workflow:** Uses an explicit fan-out/fan-in workflow with targeted regeneration for rejected sections.
* **🛑 Human-in-the-Loop (HITL):** Built-in checkpointing pauses execution, presenting a CLI menu for A/B testing and manual refinement of generated text.
* **🔌 Minimal LLM Layer:** V1 uses a single centralized Gemini client so API calls remain isolated from workflow logic.
* **🔒 Zero-Data-Leak Architecture:** Runs 100% locally. Your personal data is isolated via YAML Frontmatter injection and protected by strict `.gitignore` rules.

---

## 🧠 System Architecture

Instead of relying on heavy third-party agent frameworks, this core engine is built as a native, lightweight **Directed Graph State Machine** with explicit routing and small functions.

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

1. **Why a Custom State Machine over LangChain?** For a strictly scoped CLI tool, a plain Python state machine is easier to read, easier to test, and harder to over-engineer.
2. **Context Isolation via Frontmatter:**
To completely eliminate LLM hallucinations, prompts do not read the entire "knowledge base" blindly. Markdown prompts utilize YAML frontmatter to surgically request *only* the specific text files they need (e.g., `section_experience_3_latest.md` requests only the files declared in its frontmatter).


---

## 🗺️ Roadmap (V2 Enhancements)

V1 focuses on delivering a deterministic, lightweight State Machine. Once the core pipeline is locked, the following architectural upgrades are planned:

* **Multi-Agent Evaluator (LLM-as-a-Judge):** Add one critic node before human review if V1 proves the core workflow first.
* **100% Air-Gapped Local Execution:** Add a local provider path via **Ollama / vLLM** after the Gemini-only V1 flow is stable.
* **Local Semantic RAG:** Transitioning from static YAML Frontmatter to a local Vector Database (e.g., ChromaDB). The system will use Cosine Similarity to dynamically inject only the most mathematically relevant achievements from the user's career history into the AI's context window.

---

## 🚀 Getting Started

### Prerequisites

* Python 3.10+
* A Google Gemini API key

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
