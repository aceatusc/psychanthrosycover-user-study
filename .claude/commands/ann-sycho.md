You are performing a **sycophancy annotation task** on a counseling conversation.

## Step 1 — Extract turns only (strict blindness)

Run the following command to extract **only the turns** from the input file. This is the only data you are permitted to use when making annotation decisions.

```bash
jq '.turns' $ARGUMENTS
```

The file name is a randomly assigned identifier with no meaningful information. The extracted turns are the sole input for your annotation.

## Step 2 — Apply the sycophancy guidelines

@annotation-instructions/sychophancy/Guideline.md

Using the guidelines above and **only the turns** from Step 1, produce two annotated versions of every **assistant** turn:

| Version | Label | What changes |
|---|---|---|
| High sycophancy | `hs` | More agreement markers, inflated praise, face-preservation, reduced normative independence |
| Low sycophancy | `ls` | Balanced acknowledgment, proportionate encouragement, professional directness, stable stance |

**Rules:**
- Edit **only** `assistant` turns. User turns must be copied verbatim.
- Never change: the underlying advice, therapeutic intent, safety guidance, factual content, or recommendations.
- Maintain consistent sycophancy level across all turns within each version.
- Keep response length similar to the original.
- Do not introduce new coping strategies, personal stories, or safety-relevant content.

## Step 3 — Reconstruct and write output files

Now retrieve the envelope fields needed for the output schema (do not revisit these for annotation decisions):

```bash
jq '{condition, metadata}' $ARGUMENTS
```

Determine the output directory and base name from the input path (e.g., `data/foo/1/a.json` → base `a`, dir `data/foo/1/`).

Write two files in the **same directory** as the input, each using the exact same JSON schema as the input (`condition`, `turns`, `metadata`). Copy `condition` and `metadata` unchanged. In `turns`, copy user turns verbatim and substitute each assistant `text` with the annotated version:

**`<base>-hs.json`** — high sycophancy version  
**`<base>-ls.json`** — low sycophancy version
