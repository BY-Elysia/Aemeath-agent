# Formula Explanation

Use this guide whenever a paper contains equations, losses, algorithms, scores, update rules, metrics, routing rules, attention formulas, optimization objectives, or probability definitions.

## Formula Fidelity First

Never trust PDF-extracted equation text blindly. Extraction commonly moves transposes, breaks
fractions, loses superscripts/subscripts, and changes the scope of `Softmax`, sums, cases, or
parentheses.

For every understanding-critical formula:

1. inspect the rendered PDF equation and nearby prose
2. prefer the paper's LaTeX source when available
3. use official code to resolve implementation details, while clearly distinguishing code behavior
   from the paper's mathematical statement
4. verify operator scope, indices, ranges, and parentheses before placing the formula in the report
5. if the notation remains ambiguous, state the ambiguity instead of silently choosing an
   interpretation

Do not build a detailed explanation on top of a malformed equation.

Use `math_typography.md` to format every variable and symbolic expression that appears in the
surrounding prose. Formula fidelity includes both mathematical meaning and readable rendering.

## Standard

For each important formula, explain these things:

1. **Conceptual need**: what familiar problem or conventional calculation creates the need for
   this formula, and what behavior the formula controls.
2. **Purpose**: what quantity the formula computes and why the paper needs it.
3. **Symbols**: every important symbol, including index ranges and tensor shapes when available.
4. **Computation**: how the value is calculated step by step.
5. **Location in the method**: whether it belongs to data construction, model forward pass, training loss, inference, intervention, or evaluation.
6. **Intuition**: what the formula is doing in plain language and how it differs from the closest
   familiar objective or computation.
7. **Assumptions and limits**: what the formula assumes, ignores, or makes fragile.
8. **Implementation details**: when relevant, specify softmax axis, mask semantics, positive/negative samples, normalization, temperature, logits, pooling/averaging/max/top-k, and which parameters receive gradients.
9. **Algorithm bridge**: identify the pseudocode line or execution step that computes the formula and the next operation that consumes its result.
10. **Worked trace**: for the hardest formulas, include a small symbolic or clearly labeled explanatory numeric example that follows the operators in order.

## Explanation Pattern

Avoid saying only “the paper defines X as...”. Teach the formula from concept to calculation:

```markdown
普通/传统方法中，<familiar computation or problem>。本文需要进一步解决 <gap>，因此
这里要计算 <quantity>，它控制 <behavior>。

$$
...
$$

这个式子可以分成几步理解。第一步，...；第二步，...；第三步，...。
其中，... 表示 ...，维度是 ...；... 表示 ...。
直观上，它是在 ...。如果 <condition> 不成立，这个公式可能会 ...

解释性例子：<small symbolic or numeric walkthrough when helpful>
```

## Depth Rules

- Attention formulas: explain Q, K, V, mask, softmax axis, score matrix shape, and what is read/written.
- Loss functions: explain each term, supervision signal, optimization direction, and trade-off coefficients.
- Similarity scores: explain the compared objects, vector dimensions, normalization, dot product or cosine computation, temperature if present, and how multiple scores are pooled.
- Contrastive objectives: explain positive/negative samples, score matrix shape, score function, normalization, softmax axis, and what representation is being separated.
- RL/preference objectives: explain policy, reference model, reward/preference signal, KL or regularization terms, and update target.
- Routing/retrieval scores: explain candidates, raw logits before normalization, normalization
  axis, whether selection happens before or after normalization, whether selected weights are
  renormalized, what happens to discarded candidates, and how dispatch/combine or downstream
  consumption works.
- Evaluation metrics: explain numerator/denominator, higher/lower better, and what claim the metric can or cannot support.

## Operator-Level Audit

For every important formula, walk through each operator rather than jumping from inputs to the
final intuition:

- transpose, matrix multiplication, dot product, distance, or cosine
- normalization and its axis
- mask and its values/semantics
- top-k, max, mean, sum, concatenation, or indexing
- indicator, sampling, stop-gradient, or non-differentiable selection
- batch/token/candidate reductions
- final scalar, vector, matrix, or selected set

Symbol definitions alone do not count as a formula explanation. The reader should be able to
write the corresponding pseudocode from the explanation.

For a loss, explicitly show:

```text
model outputs -> targets/positives/negatives -> per-item term
-> reduction axes -> weighted loss -> parameters receiving gradients
```

For an auxiliary loss, also explain how it interacts with the main objective and what behavior a
larger coefficient encourages or harms.

## Pseudocode

When formulas define a process rather than a single scalar, add a compact pseudocode block after the explanation. Good candidates include:

- one training step
- one inference step
- attention mask construction
- negative sampling or reranking
- retrieval/routing candidate selection
- reward or preference optimization update

Pseudocode must use paper-grounded names. If a line depends on an implementation detail not stated in the paper, mark it as `原文未明确说明` or phrase it as an implementation assumption.

Do not use an undefined paper-specific function as a substitute for explaining a formula or mechanism. Expand important scoring, attention, routing, retrieval, loss, or update functions until the actual computation is visible.

## Formula Failure Conditions

Rewrite the explanation before delivery if:

- it only paraphrases the equation or lists symbols
- it begins with symbols before explaining why the quantity exists
- it says “compute similarity/probability/loss” without the underlying operations
- it omits a softmax/reduction axis that affects semantics
- it omits positive/negative targets, selected/discarded items, or gradient recipients
- its pseudocode computes a materially different quantity
- a technical reader could not calculate the next intermediate value
- a reader with basic LLM knowledge could perform the arithmetic but still not explain what
  behavior the formula changes or why the paper needs it

## Placement

Explain formulas where the corresponding mechanism appears in the report. Do not collect all formulas into a standalone formula section unless the user explicitly asks.
