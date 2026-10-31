# AI Finance Controller

### An AI that investigates payment mismatches, and knows when not to trust itself.

**Live demo:** https://ai-finance-controller-908.streamlit.app/

**GitHub:** https://github.com/Ankit-pro908/ai-finance-controller

A payment can be perfectly valid in one system and still look wrong when you compare it with another.

A normal reconciliation system can tell you **that** something is wrong. I wanted to answer the harder questions:

> **Why is it wrong? What evidence supports the explanation? And is it safe to fix?**

That led to the AI Finance Controller.

---

## The idea in one minute

| | |
|---|---|
| **The problem** | Two or more financial records disagree. What actually caused the difference? |
| **The idea** | Let AI propose possible causes. Never let the AI decide the financial truth. |
| **The controller** | Evidence validation, a causal consistency check, counterfactual simulation, and a safety gate |
| **The output** | `RESOLUTION_CANDIDATE` or `HUMAN_REVIEW` |
| **Safety rule** | Real financial data is never modified by the investigation |
| **Stack** | Python 3.11, pandas, Streamlit, Groq API (`openai/gpt-oss-120b`, temperature 0) |
| **Validation** | 7/7 golden cases, 5/5 unseen cases, 500/500 stress cases. [Read what these do and don't prove.](#chapter-8--what-the-numbers-say-and-what-they-do-not) |

---

# Chapter 1: The problem nobody warns you about

Every payment leaves a trail:

```text
Payment --- Fee --- Refund --- Settlement --- Ledger
```

When the money that should arrive does not match the money that actually arrived, reconciliation does what it is supposed to do: **it flags an exception.** And then the difficult part begins.

Suppose a settlement is ₹50 short. It could be:

- a wrong fee,
- a wrong refund,
- a wrong ledger entry,
- a wrong settlement value,
- or conflicting evidence.

The uncomfortable part is that **different mistakes can produce the same ₹50 difference**. Changing whichever record makes the arithmetic work is dangerous: the books look right while the real error stays hidden.

So the real question is not "do these records match?" It is:

> **Why do they disagree, what evidence supports that explanation, and is it safe to correct?**

---

# Chapter 2: The obvious idea, and why it is wrong

The obvious approach: give the payment records to an LLM and ask, "What went wrong?"

That is attractive because LLMs are good at reading messy information and generating explanations. But an LLM answer is a **plausible explanation**, not a verified financial fact. In finance a confident explanation that happens to be wrong can be more dangerous than no explanation at all.

So I built the system around one rule:

> **The AI proposes the cause. It never gets to decide.**

---

# Chapter 3: Building a controller that argues with itself

Every exception moves through the same investigation pipeline:

```text
Deterministic Reconciliation
            |
            v
    Exception Detection
            |
            v
     Evidence Retrieval
(Payment / Fee / Refund / Settlement / Ledger)
            |
            v
   Hypothesis Generation
 (AI for difficult cases, rules otherwise)
            |
            v
    Evidence Validation
            |
            v
 Causal Consistency Check
            |
            v
 Counterfactual Simulation
            |
            v
       Safety Gate
        /       \
       v         v
RESOLUTION     HUMAN
CANDIDATE      REVIEW
```

Each stage exists because the previous stage is not enough.

1. **Rules go first.** Anything a rule can establish stays deterministic: expected settlement, ledger totals, duplicate detection. The LLM should not be doing arithmetic that a formula does better.
2. **The AI has to show its work.** For difficult cases the LLM returns structured hypotheses: root cause, explanation, affected records, observed value, proposed value, causal relationship, and claimed delta. That turns a free-form answer into something the controller can inspect.
3. **Every citation is checked.** If the AI says "record `FEE00004` contains ₹220.48", the controller independently checks that the record exists and that the value is really there.
4. **The numbers must agree.** The claimed change has to explain the observed discrepancy. A ₹50 gap and a ₹200 claimed change means something is wrong. This check is necessary, but it is not treated as proof.
5. **The fix is tried on a copy.** The change is applied to a deep copy of the data and the whole reconciliation is recomputed. Did the exception disappear without creating a new inconsistency?
6. **The safety gate makes the final call.** If the explanation is supported and uniquely defensible, the result is `RESOLUTION_CANDIDATE`. Otherwise it is `HUMAN_REVIEW`.

If the AI call itself fails, the case does not silently become a resolution. The controller uses deterministic fallback hypotheses, or escalates when none exist.

---

# Chapter 4: The algorithms behind each step

This is what actually runs at each stage.

### The reconciliation identity (the deterministic core)

For every payment, the engine computes:

```text
expected_settlement = payment_amount - fee_amount - refund_amount
difference          = expected_settlement - actual_settlement
ledger_difference   = ledger_net - actual_settlement
```

For example, a payment of ₹8,524.00 with a fee of ₹220.48 and a refund of ₹2,862.92 should settle at ₹5,440.60. If ₹5,540.60 was recorded, the difference is -₹100.00 and the case becomes an exception. Each exception is then classified into a family: settlement amount, fee, refund, missing settlement, missing ledger entry, or duplicate payment.

### Evidence validation

Every record the AI cites is looked up by source and ID. The controller checks that the record exists, that the field exists, and that the observed value matches. A hypothesis that cites something that is not there is rejected before any money logic runs.

### The causal consistency check

The check works in magnitudes, with a tolerance of ₹0.01. For a proposed change on an existing record it computes `proposed_value - observed_value`, then requires three things to agree:

- the size of the counterfactual change matches the size of the observed discrepancy,
- the AI's claimed delta matches the observed discrepancy,
- the claimed delta matches the counterfactual change.

When a hypothesis touches several records, their absolute changes are summed. It handles three relationship types: a change to an existing record (`RECORD_DELTA`), a missing record (`MISSING_RECORD`), and a duplicate (`DUPLICATE_RECORD`). The result is one of `CAUSAL_CANDIDATE`, `NOT_SUPPORTED`, `REJECTED`, `UNVERIFIABLE`, or a pending status that waits for simulation. A `CAUSAL_CANDIDATE` is explicitly **not** treated as proven.

### Counterfactual simulation

The simulator copies all source datasets, applies the hypothetical operation (`SET_VALUE` on an existing field or `ADD_RECORD` for a missing one), and reruns the **entire** reconciliation. It reports the before and after state, whether the exception cleared, and whether the difference improved. Success means the whole financial picture is coherent afterwards, not just one number.

### The safety gate

`decision_policy.py` converts AI output and deterministic signals into a controller decision. It looks at the AI's confidence and its own "is the evidence sufficient" flag, together with evidence completeness, citation validity, and conflicts between records. Missing evidence, invalid citations, conflicts, or competing explanations lead to `HUMAN_REVIEW`.

### The AI layer

- **Model:** `openai/gpt-oss-120b` on Groq, `temperature=0`. It is a general-purpose model guided by payment-specific prompts and a response schema. It is **not** fine-tuned on payment data.
- **Bounded retries:** at most 2 API attempts per call, then a safe fallback.
- **Validated output:** responses are parsed and checked before use.
- **Near-deterministic:** temperature 0 helps, but LLM output can still vary between runs.

### Investigation modes

Every case records how it was investigated:

| Mode | Meaning |
|---|---|
| `DETERMINISTIC` | Settled by rules. No LLM call. |
| `AI` | The LLM generated hypotheses that went through the full pipeline. |
| `AI_FALLBACK_DETERMINISTIC` | The AI path failed (for example a missing API key), so deterministic fallback hypotheses were used. |

---

# Chapter 5: From seven cases to five hundred

I did not start with 500 cases. I started with seven.

### Layer 1: Golden cases

Seven hand-built, representative cases, each showing one behavior the controller must get right:

| Case | Scenario |
|---|---|
| G001 | Settlement amount error |
| G002 | Fee amount error |
| G003 | Refund amount error |
| G004 | Missing settlement |
| G005 | Missing ledger entry |
| G006 | Duplicate payment |
| G007 | Conflicting evidence (must stay in human review) |

G007 matters most. A controller that resolves everything is easy to build. The golden suite includes a case that must **not** be resolved.

### Layer 2: Generalizing the logic

A rule that only works on G001 is a hard-coded answer, not an algorithm. So I generalized the logic behind each golden case into a rule for its whole exception family, one that works for any payment, any amount, and any record IDs. The six stress families (settlement amount, fee, refund, missing settlement, missing ledger entry, duplicate payment) mirror G001 to G006.

### Layer 3: Stress

The generalized rules were then run against a 500-case benchmark spread across those six families. This is where regressions and inconsistent paths show up that a small demo never reveals.

### Layer 4: Unseen

Finally, a separate set of cases the rules were not built around: duplicate fee records, conflicting fee records, compound fee and ledger problems, compound fee and refund problems, and an unexpected ledger adjustment. These test whether the safety logic holds in new combinations.

```text
7 golden cases  ->  generalized rules  ->  500 stress cases  ->  5 unseen cases
 (what is right)     (the algorithms)      (does it scale?)     (does it hold up?)
```

---

# Chapter 6: Where it broke, and what that taught me

The final design came from failures. The most useful bugs were not syntax errors. They were cases where the system was **technically plausible but logically unsafe**. The full log is in [`docs/development-notes.md`](docs/development-notes.md).

## When two answers cleared the same gap (S002)

The true root cause was a fee error. The AI also produced a refund explanation. Both changes could make the same ₹50 discrepancy disappear in simulation.

The early controller saw two surviving explanations and escalated to a human. That was cautious, but the benchmark expected a unique resolution. The lesson was **not** to loosen the safety rule. It was to tighten the distinction between:

```text
"this change fixes the arithmetic"
```

and:

```text
"this cause is independently supported by the evidence"
```

Counterfactual success alone no longer makes a hypothesis equivalent to a fully supported cause.

## When a fix looked right but wasn't

Another hypothesis changed a ledger fee entry to match the fee source. The local ledger arithmetic improved, but the new state created an inconsistency between ledger and settlement.

> **A local improvement is not a resolution.**

The entire reconciliation state must stay coherent after the simulated correction.

## When the unseen cases exposed an early weakness

The unseen suite showed that the first version could find a mathematically valid explanation and still make the wrong operational decision. That led to four changes:

- evidence support is checked before resolution,
- competing explanations remain visible,
- simulation success alone is not treated as proof of root cause,
- ambiguous cases are escalated rather than forced.

---

# Chapter 7: Two cases that explain the system

These are real outputs from the unseen suite.

## Case A: the fix that sounded right (U002)

The ledger is ₹25 short of the settlement. A hypothesis says a settlement ledger entry is missing and proposes adding one for ₹4,065.04.

| | Before | After the simulated fix |
|---|---|---|
| Ledger net | 4,040.04 | 8,105.08 |
| Ledger difference | -25.00 | +4,040.04 |
| Exception cleared | No | No |

The simulation returns `NO_RESOLUTION`. The proposed correction made the full financial state worse, so the controller returns `HUMAN_REVIEW`.

> **A plausible explanation is not enough. The correction has to survive the whole financial model.**

## Case B: two fixes, one gap (U005)

```text
Expected settlement: ₹5,440.60
Recorded settlement: ₹5,540.60
Gap:                 ₹100
```

Two different hypotheses each eliminate the same ₹100 difference in simulation:

| Hypothesis | Change |
|---|---|
| H1: wrong fee | ₹220.48 to ₹120.48 |
| H2: wrong refund | ₹2,862.92 to ₹2,762.92 |

The arithmetic alone cannot say which one is the real cause. The controller refuses to guess:

```text
HUMAN_REVIEW
```

That is exactly the behavior I want from a finance controller.

---

# Chapter 8: What the numbers say, and what they do not

| Layer | Cases | Result |
|---|---|---|
| Golden | 7 | **7 / 7** |
| Unseen | 5 | **5 / 5** (4 used the AI path, 1 deterministic) |
| Stress | 500 | **500 / 500** (488 deterministic, 12 AI) |

Unseen and stress results were produced on 31 October 2026 at commit `f1c60e1`, with the Groq API key set.

### Stress breakdown

| Exception type | Cases | Passed |
|---|---:|---:|
| DUPLICATE_PAYMENT | 108 | 108 |
| FEE_MISMATCH | 86 | 86 |
| MISSING_LEDGER_ENTRY | 92 | 92 |
| MISSING_SETTLEMENT | 104 | 104 |
| REFUND_MISMATCH | 17 | 17 |
| SETTLEMENT_AMOUNT_MISMATCH | 93 | 93 |

Decision accuracy, resolution-path accuracy, and operation accuracy are all 100% on the stress suite.

### Unseen breakdown

| Case | Scenario | Mode | Expected | Actual |
|---|---|---|---|---|
| U001 | Compound fee and ledger inconsistency | AI | HUMAN_REVIEW | HUMAN_REVIEW |
| U002 | Unexpected ledger adjustment | DETERMINISTIC | HUMAN_REVIEW | HUMAN_REVIEW |
| U003 | Duplicate fee record | AI | HUMAN_REVIEW | HUMAN_REVIEW |
| U004 | Conflicting fee records | AI | HUMAN_REVIEW | HUMAN_REVIEW |
| U005 | Compound fee and refund exception | AI | HUMAN_REVIEW | HUMAN_REVIEW |

### The important context

I do **not** want these numbers to imply more than they prove.

- **The 500/500 mostly validates the deterministic engine.** Only 12 of 500 cases (2.4%) reached the LLM. That is by design: known financial relationships should not need a language model.
- **The unseen suite currently tests knowing when to stop.** All five cases are meant to end in `HUMAN_REVIEW`, so a controller that always escalated would also score 5/5. It does not yet prove that new cases can be resolved correctly.
- **The stress suite is a regression test, not a blind test.** Failures it found, such as S002, were fixed during development.
- **All data is synthetic.** The records were generated for this project and the errors were injected deliberately. That makes the benchmark reproducible, but it is not production financial data. The ground truth and the controller share an author.
- **The causal check works on magnitudes.** It does not independently verify the claimed direction (increase or decrease), so simulation is the real protection against a wrong-direction fix.
- **The AI can still be wrong.** The independent checks reduce the chance of an unsafe conclusion. They do not eliminate model errors. That is why the safety gate exists.

---

# Chapter 9: The seven rules I ended up with

1. **Deterministic first.** Known financial relationships use rules.
2. **Evidence before conclusions.** Every explanation needs supporting records.
3. **Validate every citation.** Record IDs and values must match the source.
4. **Check the arithmetic.** The proposed cause must explain the observed gap.
5. **Simulate before resolving.** A proposed fix has to survive counterfactual testing.
6. **Never guess through ambiguity.** Competing explanations go to a human.
7. **Never touch real financial data.** Investigation changes remain hypothetical until explicit downstream approval.

Human review is the right answer when explanations compete, evidence is incomplete, a citation cannot be validated, source records conflict, the AI itself says the evidence is insufficient, or a fix does not survive full simulation. Abstention is a feature, not a failure.

---

# Chapter 10: Try it yourself

## Live demo

**Open the application:** https://ai-finance-controller-908.streamlit.app/

A good demo path:

```text
Evaluation & Generalization
        |
        v
S002  ->  Evidence  ->  Hypotheses  ->  Causal Verification
        ->  Counterfactual Simulation  ->  Resolution Candidate
```

Then try a conflicting or unseen case and watch it end in `HUMAN_REVIEW`. Finally, open the stress benchmark and select any case from the 500-case universe.

## Run it locally

```bash
git clone https://github.com/Ankit-pro908/ai-finance-controller.git
cd ai-finance-controller
python -m venv .venv
```

Activate the environment:

```bash
# Windows PowerShell
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
pip install pytest
```

Set the Groq API key (never commit it):

```bash
# Windows PowerShell
$env:GROQ_API_KEY = "your_key"
# macOS / Linux
export GROQ_API_KEY="your_key"
```

Without a key everything still runs, but cases that need the LLM fall back to the deterministic path (`AI_FALLBACK_DETERMINISTIC`).

Run the application and the validation suites:

```bash
streamlit run app.py
python tests/run_unseen.py
python tests/stress_runner.py     # LLM cases call the live API, so this can be slow
pytest -q
```

On Windows PowerShell, run `$env:PYTHONUTF8 = "1"` first if the stress runner fails with a `UnicodeEncodeError`.

Tested with Python 3.11, streamlit 1.63.0, pandas 3.0.5, numpy 2.4.6, groq 1.7.0, pytest 9.1.1.

---

# Where things live

```text
ai-finance-controller/
├── app.py                   # Streamlit investigation console
├── src/
│   ├── reconciliation/      # deterministic engine and evaluator
│   ├── evidence/            # retrieval, completeness, consistency
│   ├── ai/                  # Groq client, investigator, validators, decision policy
│   ├── controller/          # orchestrator, causal verifier, simulator, deterministic resolver
│   └── *_generator.py       # synthetic data, exception injection, ground truth
├── data/                    # base tables, injected exceptions, stress and unseen cases
├── tests/                   # unseen and stress runners, golden evaluator, unit tests
├── scripts/                 # manual scripts that call the live Groq API
└── docs/                    # development notes: the full debugging story
```

---

# What comes next

The next version should become more capable **without becoming less safe**.

1. **More meaningful unseen testing.** Add unseen cases that should end in `RESOLUTION_CANDIDATE`, so the suite tests both "can it resolve a new case?" and "can it abstain from an unsafe one?". Keep a blind set that is never used for tuning, and report false-resolution rate and correct-abstention rate separately.
2. **A fair comparison.** Run rules-only, LLM-only, and the full controller on the same cases to show what each layer adds.
3. **Historical resolution memory.** When a human approves a resolution, store it as a structured precedent that similar future cases can retrieve.
4. **Payment-domain intelligence.** A model adapted to the payment lifecycle, fees, refunds, settlements, and ledger events, using trusted historical investigations as context.
5. **Human-in-the-loop learning.** Approved resolutions become feedback for future investigations.
6. **Production governance.** Approval workflows, role-based access, immutable audit logs, model version tracking, monitoring, and controlled write-back.

One boundary should never move:

> **Learning must never bypass evidence validation, causal verification, counterfactual simulation, or the final safety gate.**

---

# The point of the project

The interesting part is not that an LLM can explain a payment mismatch. LLMs can do that.

The interesting part is what happens **after** the model gives an explanation. Is the evidence real? Does the explanation match the numbers? Does the proposed correction survive simulation? Is there one defensible explanation? If the answer to any of these is no, a human decides.

> **AI proposes. Evidence verifies. Simulation tests. Safety decides.**

That is the AI Finance Controller.

---

Built by Ankit ([@Ankit-pro908](https://github.com/Ankit-pro908)). Released under the MIT License. See [LICENSE](LICENSE).
