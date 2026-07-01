# Limitations and Future Work

Use this guide when reading limitations, discussion, conclusion, failure cases, broader impact, ethical considerations, appendix notes, and future-work statements.

The report must explain the limitations and outlook stated by the paper itself. It may also add careful analysis, but author-stated points and report-level analysis must never be blended together.

## Where to Look

Do not rely only on a section named `Limitations`. Inspect:

- abstract and introduction for declared scope
- method assumptions and intentionally excluded cases
- experiment setup, missing evaluations, negative results, and failure cases
- ablations that reveal fragile modules or dependencies
- discussion, conclusion, future work, broader impact, and ethical considerations
- appendix implementation notes and unresolved questions

Search for language such as:

- limitation, drawback, challenge, failure, risk, concern
- does not, cannot, fails to, limited to, only supports
- left for future work, future direction, plan to, aim to, remain open
- due to, depends on, requires, assumes, inherits

## Required Distinction

Classify each point internally as one of:

1. **Author-stated limitation**: the paper explicitly acknowledges a weakness, failure, assumption, excluded setting, or risk.
2. **Author-proposed future work**: the paper explicitly states a next step, planned extension, mitigation, or open research direction.
3. **Experiment-supported boundary**: results or ablations reveal a boundary even if the authors do not label it a limitation.
4. **Report analysis**: a cautious implication derived from the architecture or missing evaluation.

In the final report, make the distinction natural but unmistakable. Use phrases such as `作者明确指出`、`实验显示`、`作者提出的后续方向是`、`从架构上进一步看`.

Do not present report analysis as the authors' own claim.

## Limitation Explanation Standard

For each important limitation, explain:

- what the limitation is
- whether it is explicitly stated by the authors
- which architecture component, assumption, dataset, metric, or experimental setting causes it
- when it matters in practice
- what evidence or failure case reveals it
- which claims remain valid despite the limitation
- whether the paper proposes a mitigation

Avoid generic statements such as `需要更多实验` or `未来可扩大数据集` unless the paper states them or the report explains exactly which missing evidence motivates them.

## Future-Work Explanation Standard

For each author-proposed future direction, explain:

- the exact unresolved problem it addresses
- how it connects to the current method's limitation
- what component, data, objective, evaluation, or deployment setting would need to change
- what capability or evidence the proposed direction could add
- whether the paper gives a concrete plan or only a broad suggestion

If the paper does not explicitly propose future work, write `原文未明确提出后续研究方向` rather than inventing one.

## Recommended Report Organization

Use one integrated section such as:

```markdown
## 局限、作者展望与适用边界

### 作者明确指出的不足
...

### 作者提出的后续方向
...

### 从实验和架构中还能看到的边界
...
```

Do not force empty subsections. If the paper has only one or two points, explain them as connected prose.

## Grounding Rules

- Ground author-stated limitations and future work in the paper's wording or nearby evidence.
- Preserve uncertainty: `作者认为` is not the same as `实验证明`.
- Do not invent promised datasets, model changes, safety mitigations, or deployment plans.
- If a limitation appears only in official code or an external source, label that source explicitly; do not attribute it to the paper.
