# ABoHJ User Study — Annotation Project

## Overview

This project annotates AI-generated counseling conversations along two dimensions — **sycophancy** and **anthropomorphism** — for a user study on how these properties affect mental health support quality.

Each dimension has independent high/low versions of the therapist responses while holding advice, therapeutic intent, safety guidance, and factual content constant.

## Directory structure

```
data/
  <category>/          # 7 mental health use-case categories
    <1|2>/
      a.json           # one conversation (professional or unprofessional condition)
      b.json           # paired conversation (same user turns, different therapist style)
annotation-instructions/
  sychophancy/
    Guideline.md       # canonical annotation rules for sycophancy (source of truth)
    Operationalization.md
  anthropomorphism/
    Guideline.md       # canonical annotation rules for anthropomorphism (source of truth)
    Operationalization.md
background.md          # literature review and category rationale
```

## Data format

Each `*.json` file:
```json
{
  "condition": "professional" | "unprofessional",
  "turns": [
    { "role": "user", "text": "..." },
    { "role": "assistant", "text": "..." }
  ],
  "metadata": { "reasons": ["..."] }
}
```

## Annotation commands

### `/ann-sycho <path>`
Annotates a single conversation for **sycophancy**.  
Produces two files next to the input:
- `<base>-hs.json` — high sycophancy (more agreeable, flattering, face-preserving)
- `<base>-ls.json` — low sycophancy (professionally independent, calibrated)

### `/ann-anth <path>`
Annotates a single conversation for **anthropomorphism**.  
Produces two files next to the input:
- `<base>-ha.json` — high anthropomorphism (more human-like: first-person, empathic, warm)
- `<base>-la.json` — low anthropomorphism (impersonal: neutral, declarative, no relational markers)

**Example:**
```
/ann-sycho data/advice-seeking-and-coping-strategies/1/a.json
# writes: data/advice-seeking-and-coping-strategies/1/a-hs.json
#         data/advice-seeking-and-coping-strategies/1/a-ls.json
```

## Annotation constraints (apply to both commands)

- Edit **only** assistant turns. User turns are never modified.
- Each annotation is **blind** to the `condition` field and file name — do not let them influence edits.
- Each annotation is **independent** of all other annotations on the same file.
- The sole source of truth is the relevant `Guideline.md`.
- Never alter: underlying advice, safety guidance, therapeutic intent, factual content, or recommendations.
- Output JSON schema is identical to input schema (`condition`, `turns`, `metadata`).
