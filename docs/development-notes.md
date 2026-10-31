# AI Finance Controller

**🚀 Live Demo:** https://ai-finance-controller-908.streamlit.app/

**📦 GitHub:** https://github.com/Ankit-pro908/ai-finance-controller


## Evidence-First Investigation and Resolution of Payment Reconciliation Exceptions

An AI-assisted financial investigation controller that starts with deterministic reconciliation, investigates difficult exceptions using a payment-focused LLM, validates the evidence behind every hypothesis, checks whether the proposed cause is actually causal, tests hypothetical corrections through counterfactual simulation, and only then decides between a **Resolution Candidate** and **Human Review**.

> **Core principle:** AI proposes the cause; evidence, causality, simulation, and safety controls decide whether the case is safe to resolve.

---

## 1. Project Name / Title

**AI Finance Controller — Evidence-First Investigation and Resolution of Payment Reconciliation Exceptions**

---

## 2. Project Objectives

The project was built to investigate the difficult cases that remain after normal financial reconciliation identifies an exception.

### Objectives

- Detect and classify payment reconciliation exceptions across payments, fees, refunds, settlements, and ledger entries.
- Use AI to generate multiple plausible root-cause hypotheses for difficult exceptions.
- Require every hypothesis to be grounded in retrievable financial evidence.
- Independently validate cited record IDs and observed values.
- Verify that the proposed cause explains the observed discrepancy.
- Run counterfactual simulations before accepting a resolution candidate.
- Escalate ambiguous, conflicting, or insufficiently supported cases to human review.
- Keep hypothetical corrections separate from real financial data.
- Evaluate the controller on representative, unseen, and large-scale stress cases.

---

## 3. What Does It Solve?

Traditional reconciliation can tell us **that two financial records do not match**. The harder operational question is:

> **Why do they disagree, what evidence supports the explanation, and is it safe to correct the discrepancy?**

This project addresses that investigation problem.

A single payment can be represented across multiple financial sources:

```text
Payment
   |
   +---- Fee
   |
   +---- Refund
   |
   +---- Settlement
   |
   +---- Ledger
```

An exception can have more than one plausible explanation. For example, a ₹50 settlement discrepancy could potentially be explained by a fee error, refund error, ledger error, or another missing/conflicting record.

The controller therefore does not treat an LLM response as financial truth. It uses AI for **investigation and hypothesis generation**, while the controller remains responsible for validation and the final decision.

---

## 4. Why This Is an AI Finance Controller Rather Than an LLM Wrapper

The system is intentionally hybrid.

```text
Deterministic Financial Logic
          |
          v
Exception Detection
          |
          v
Evidence Retrieval
          |
          v
AI Hypothesis Generation
          |
          v
Evidence Validation
          |
          v
Causal Verification
          |
          v
Counterfactual Simulation
          |
          v
Safety Gate
          |
          +------------------+
          |                  |
          v                  v
Resolution Candidate     Human Review
```

The AI does not have authority to directly change financial records.

---

## 5. End-to-End Investigation Flow

### Step 1 — Deterministic reconciliation

The controller first calculates expected settlement values and compares them with the observed settlement and ledger state.

Examples of detected exceptions include:

- settlement amount mismatch
- fee mismatch
- refund mismatch
- missing settlement
- missing ledger entry
- duplicate payment
- conflicting evidence

### Step 2 — Evidence retrieval

For an exception, the controller retrieves the relevant payment, fee, refund, settlement, and ledger records.

### Step 3 — AI investigation

For difficult exceptions, the LLM generates structured hypotheses rather than a single unconstrained answer.

A hypothesis includes concepts such as:

- root cause
- explanation
- affected records
- observed values
- proposed counterfactual values
- causal relationship

### Step 4 — Evidence validation

The controller independently checks whether every cited record exists and whether the claimed observed values agree with the source data.

### Step 5 — Causal verification

A mathematically plausible explanation is not enough. The controller checks whether the claimed delta is consistent with the actual reconciliation discrepancy and the affected financial records.

### Step 6 — Counterfactual simulation

The proposed correction is applied only inside a temporary simulation.

The controller asks:

> If this record were changed in the proposed way, would the financial exception actually disappear without introducing a new inconsistency?

### Step 7 — Safety gate

A resolution candidate is allowed only when the explanation is sufficiently supported and uniquely defensible.

Ambiguity, conflicting evidence, invalid citations, incomplete evidence, or insufficient support leads to **Human Review**.

### Step 8 — Final decision

The controller returns one of the operational outcomes used by the project:

- **RESOLUTION_CANDIDATE**
- **HUMAN_REVIEW**

The actual financial data is not modified by the counterfactual investigation.

---

## 6. The Seven Golden Rules

These are the design rules that govern how the controller is allowed to reason and resolve.

1. **Deterministic First** — known financial relationships should be handled by deterministic controls whenever possible.
2. **Evidence Before Conclusions** — a plausible explanation must be grounded in actual records.
3. **Validate Every Citation** — cited record IDs and observed values must match source data.
4. **Prove Causality** — the proposed cause must explain the observed financial delta.
5. **Simulate Before Resolving** — a proposed correction must survive counterfactual testing.
6. **Never Guess Through Ambiguity** — materially competing explanations should be escalated to human review.
7. **Never Modify Real Financial Data** — investigation changes remain hypothetical until an explicit downstream approval process exists.

---

## 7. What the Investigation UI Shows

The Streamlit application is designed as an investigation console rather than a raw technical debugger.

A reviewer can select a case and see:

```text
Case / Payment
      |
      v
Financial exception
      |
      v
Payment -> Fee -> Refund -> Settlement -> Ledger
      |
      v
Candidate hypotheses
      |
      v
Evidence validation
      |
      v
Causal verification
      |
      v
Counterfactual simulation
      |
      v
Safety gate
      |
      v
Final Controller Decision
```

The user-facing interface presents these as readable explanations, status lines, financial amounts, and verification outcomes rather than exposing raw JSON.

---

## 8. Representative / Golden Cases

The project has a small representative suite designed to exercise the core controller behaviors.

The seven representative scenarios include:

| Case | Scenario |
|---|---|
| G001 | Settlement amount error |
| G002 | Fee amount error |
| G003 | Refund amount error |
| G004 | Missing settlement |
| G005 | Missing ledger entry |
| G006 | Duplicate payment |
| G007 | Conflicting evidence |

The conflicting-evidence case is intentionally expected to remain under human review rather than being forced into an automatic resolution.

These cases serve two purposes:

1. validate the controller contract,
2. provide simple, explainable examples for the live demo.

---

## 9. Unseen Cases and Generalization

The project also contains a separate unseen-case suite.

The purpose of these cases is not to repeat the seven representative scenarios. It is to test whether the controller's rules generalize to new combinations and new evidence patterns.

The unseen suite contains:

```text
U001
U002
U003
U004
U005
```

### What happened during development

The unseen suite exposed an important weakness in early versions of the controller: the system could sometimes find a mathematically valid explanation and still make the wrong operational decision.

For example, one unseen case exposed a situation where the controller could treat a proposed correction as sufficient even though the broader evidence structure still indicated ambiguity or missing support.

This led to changes in the safety decision path so that:

- evidence support is checked before resolution,
- conflicting explanations remain visible,
- counterfactual success alone is not treated as proof of the correct root cause,
- ambiguous cases are escalated instead of being forced into resolution.

The unseen suite therefore became an important **generalization and safety test**, not just another accuracy dataset.

> The exact pass/fail count shown in the final UI should always come from the latest executed unseen evaluator output rather than being hard-coded.

---

## 10. 500-Case Stress Benchmark

The controller was also evaluated against a 500-case benchmark spanning multiple exception patterns.

The validated benchmark result used for the final project is:

```text
TOTAL: 500
PASSED: 500
FAILED: 0
PASS RATE: 100%
```

The benchmark was particularly useful because it caught problems that were not obvious in small demos.

The final passing run demonstrated that the controller could keep the deterministic and AI paths consistent enough to satisfy the project contract across the full benchmark.

---

## 11. Important Debugging Journey

The final system was not reached in one step. Several concrete failures during development helped shape the architecture.

### 11.1 Missing benchmark-case directory

An early stress runner attempted to investigate an unseen case using a path such as:

```text
data/stress/cases/U001
```

when the unseen dataset actually lived under:

```text
data/unseen/cases/U001
```

The issue was fixed by separating the dataset roots and making the case loader explicitly select the correct directory for `stress`, `unseen`, and representative cases.

### 11.2 Missing unseen case files

A direct test initially failed because the loader looked for:

```text
data/unseen/U001/payments.csv
```

while the actual case structure was:

```text
data/unseen/cases/U001/payments.csv
```

The loader and UI were corrected to use the actual case hierarchy.

### 11.3 Unseen TypeError in the Streamlit UI

The dashboard initially constructed a path using string concatenation/division logic that produced:

```text
TypeError: unsupported operand type(s) for /: 'str' and 'str'
```

The fix was to construct paths from `Path` objects consistently:

```python
PROJECT_ROOT / "data" / "unseen"
```

instead of attempting to divide strings.

### 11.4 Golden cases accidentally redirected to the stress suite

The first version of the evaluation UI reused the stress-case state when an evaluator clicked a Golden case.

This caused a Golden investigation to jump into the `S001...S500` stress dataset.

The fix was to persist the evaluation dataset type in session state and make the investigation loader context-aware:

```text
Golden -> representative dataset
Unseen  -> unseen dataset
Stress  -> stress dataset
```

All three paths then enter the same shared controller investigation workspace.

### 11.5 AI hypothesis competition caused false human-review outcomes

One of the most useful debugging cases was `S002`.

The correct root cause was a fee amount error. The AI could also produce an alternative refund explanation whose counterfactual simulation happened to clear the same ₹50 discrepancy.

In an early version, this meant multiple hypotheses survived and the controller correctly became conservative by returning `HUMAN_REVIEW` — but the benchmark expected a unique resolution candidate for that scenario.

The investigation logic was then tightened so that candidate hypotheses were merged, validated, and simulated in a way that preserved the distinction between:

- a hypothesis that merely produces the right arithmetic result,
- a hypothesis that is independently supported by the evidence and causally consistent.

After this correction, `S002` produced:

```text
H1  Fee amount error        -> SUCCESS
H2  Refund alternative     -> rejected by final safety/verification path

Final decision: RESOLUTION_CANDIDATE
```

### 11.6 Ledger correction could improve one view while making another inconsistent

Another important example was a ledger hypothesis that changed a ledger fee entry to match the fee source. The change could improve the ledger arithmetic while simultaneously creating a new ledger-to-settlement inconsistency.

The controller therefore learned to require the full reconciliation state after simulation to remain coherent rather than accepting a local improvement.

### 11.7 Long investigation labels broke the UI

Labels such as:

```text
SETTLEMENT_AMOUNT_MISMATCH
```

and long investigation modes wrapped badly inside KPI cards.

The UI was adjusted so that long financial labels use smaller, controlled typography and readable labels rather than being forced into narrow fixed-width cards.

---

## 12. Example: End-to-End AI Investigation

A representative AI case can be summarized as:

```text
Exception:
FEE_MISMATCH

Observed discrepancy:
₹50

Evidence:
Payment + Fee + Refund + Settlement + Ledger

AI hypothesis H1:
The recorded fee is incorrect.

Evidence validation:
PASSED

Causal verification:
PASSED

Counterfactual:
Fee ₹16.96 -> ₹66.96

Before:
EXCEPTION / ₹50 discrepancy

After:
MATCH / ₹0 discrepancy

Final:
RESOLUTION_CANDIDATE
```

The corresponding development run showed the fee correction clearing the exception while the competing ledger correction failed to clear the overall reconciliation state.

---

## 13. Human Review and Safe Abstention

A finance controller should not be judged only by how often it resolves a case.

It must also know when **not** to resolve.

Human review is appropriate when, for example:

- multiple materially plausible explanations remain,
- evidence is incomplete,
- cited values cannot be validated,
- source records conflict,
- the AI says the evidence is insufficient,
- or a proposed correction does not survive full counterfactual verification.

The controller therefore uses abstention as a feature, not a failure.

---

## 14. Evaluation Strategy

The evaluation structure was designed in layers.

### Layer 1 — Representative / Golden

Validates the core decision contract on a small set of interpretable scenarios.

### Layer 2 — Unseen

Tests whether the same reasoning and safety rules generalize to new cases that were not part of the representative examples.

### Layer 3 — Stress

Runs the controller over a much larger case population to expose regression, inconsistent paths, and AI-related failure modes.

The key idea is:

```text
Representative behavior
        +
Generalization
        +
Large-scale regression
        =
More credible controller validation
```

---

## 15. Architecture Components

A simplified project structure is:

```text
ai-finance-controller/
│
├── app.py
│
├── data/
│   ├── payments.csv
│   ├── fees.csv
│   ├── refunds.csv
│   ├── settlements.csv
│   ├── ledger.csv
│   ├── stress/
│   │   ├── ground_truth.csv
│   │   └── cases/
│   │       ├── S001/
│   │       └── ...
│   └── unseen/
│       ├── ground_truth.csv
│       └── cases/
│           ├── U001/
│           └── ...
│
├── src/
│   ├── reconciliation/
│   ├── evidence/
│   ├── ai/
│   └── controller/
│
└── tests/
    ├── stress_runner.py
    └── run_unseen.py
```

Key responsibilities include:

- **Reconciliation engine** — deterministic financial calculations and exception classification.
- **Evidence retriever** — gathers relevant records.
- **AI investigator** — produces structured financial hypotheses.
- **Evidence validator** — independently validates AI citations.
- **Causal verifier** — checks whether a hypothesis explains the discrepancy.
- **Simulator** — runs hypothetical corrections without modifying the source data.
- **Controller/orchestrator** — coordinates the full investigation and final decision.
- **Streamlit app** — exposes the process through a human-readable interface.

---

## 16. AI Reliability and Fallback

LLM calls are bounded rather than allowed to retry indefinitely.

The investigation path uses a limited number of attempts, validates the result, and escalates safely when AI cannot produce a usable investigation response.

This means an API failure should not silently become a financial resolution.

The intended behavior is:

```text
AI request
   |
   v
Response validation
   |
   +---- valid ----> continue investigation
   |
   +---- invalid --> bounded retry
                         |
                         +---- valid -> continue
                         |
                         +---- still invalid -> safe fallback / human review
```

---

## 17. Technology Stack

- Python
- Pandas
- Streamlit
- Groq API
- Payment-focused LLM investigation layer
- Deterministic reconciliation rules
- Counterfactual simulation
- CSV-based synthetic financial datasets for evaluation

The current AI integration uses the Groq client and a configurable model name in `src/ai/client.py`.

---

## 18. Future Scope

The most important future step is turning the current controller into a **payment-domain intelligence system that improves from real investigation history while preserving the same safety boundaries**.

### 18.1 Payment-domain AI

The current MVP uses an LLM as an investigation component. A production evolution would adapt or fine-tune a model around payment-specific concepts such as:

- payment lifecycle
- fees
- refunds
- settlements
- ledger events
- reconciliation patterns
- historical exception types

The goal is a model that understands payment investigations more deeply than a general-purpose model.

### 18.2 Historical Resolution Memory

Every approved investigation can become a structured precedent:

```text
Exception
   + Evidence
   + Root Cause
   + Approved Resolution
   + Reasoning Metadata
             |
             v
      Resolution Memory
```

A future case could retrieve similar historical cases before generating new hypotheses.

### 18.3 Human-in-the-Loop Learning

This is the intended learning loop:

```text
New Exception
       |
       v
Payment-domain AI investigation
       |
       v
Evidence + Causal + Simulation checks
       |
       v
Enough support?
    /        \
  YES         NO
   |           |
   v           v
Resolution   Human Review
Candidate        |
                 v
        Human-approved resolution
                 |
                 v
          Resolution Memory
                 |
                 v
       Better future investigations
```

When a human reviews a case, the system can capture the approved outcome as structured feedback for future retrieval, ranking, or model improvement.

### 18.4 Unknown-case behavior

A key design goal is that the future system should recognize when it has insufficient knowledge or evidence.

It should be able to say:

> “I do not have enough evidence or a sufficiently supported precedent to resolve this safely.”

and route the case to a human.

### 18.5 Continuous evaluation

As historical data grows, the system should continuously monitor:

- resolution accuracy
- correct abstention rate
- false resolution rate
- evidence completeness
- citation validity
- causal verification success
- investigation latency
- model/version performance

### 18.6 Production controls

For a real finance platform, the next layer would include:

- approval workflows
- role-based access
- immutable audit logs
- model/version tracking
- real payment and settlement integrations
- asynchronous investigation queues
- production monitoring and observability
- explicit rollback / approval controls

### 18.7 Safety boundary remains independent

The learning system should improve future investigation quality, but it should never be able to bypass the controller's safety gates.

```text
Learning
   |
   v
Better hypotheses / retrieval
   |
   X  cannot bypass
   |
   v
Evidence validation
Causal verification
Counterfactual simulation
Safety gate
```

This separation is essential for a financial system.

---

## 19. How to Run

Install dependencies in the project environment, then launch the Streamlit application.

```powershell
streamlit run app.py
```

For validation, the project also contains dedicated scripts for the benchmark and unseen suites.

Example patterns include:

```powershell
python tests/run_unseen.py
```

and the stress-runner / benchmark commands used by the project test harness.

---

## 20. What to Demonstrate in a Live Review

A strong live walkthrough is:

### Demo 1 — Representative case

Open a Golden case and show:

```text
Exception
-> Evidence
-> Hypotheses
-> Validation
-> Simulation
-> Resolution Candidate / Human Review
```

### Demo 2 — Unseen case

Open one of the U001–U005 cases and explain that these cases test generalization beyond the representative examples.

### Demo 3 — Large benchmark

Show:

```text
500 total
500 passed
0 failed
100% controller pass rate
```

### Demo 4 — Safety behavior

Open a conflicting/ambiguous case and show that the controller prefers human review instead of guessing.

---

## 21. Key Differentiator

Most AI prototypes stop at:

```text
LLM -> answer
```

This project deliberately goes further:

```text
LLM
 |
 v
Hypothesis
 |
 v
Evidence validation
 |
 v
Causal verification
 |
 v
Counterfactual simulation
 |
 v
Safety gate
 |
 +--------------------+
 |                    |
 v                    v
Resolve              Review
```

That is the central idea behind the AI Finance Controller.

---

## 22. Final Summary

The project started as a reconciliation problem and evolved into an evidence-first financial investigation controller.

The main engineering lesson was that **a plausible financial explanation is not necessarily a safe financial decision**.

The final design therefore separates:

- deterministic computation from AI reasoning,
- hypothesis generation from hypothesis acceptance,
- mathematical correctness from causal support,
- simulation from real-world modification,
- and automation from human accountability.

The current benchmark demonstrates the controller can operate at scale, while the generalized and unseen suites are intended to test whether the same safety and reasoning principles continue to hold beyond the simplest representative examples.

> **AI investigates. Evidence verifies. Simulation proves. The controller decides.**
