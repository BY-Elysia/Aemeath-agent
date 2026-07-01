# Reader Model And Pedagogy

Use this guide for every report. The default reader has basic deep-learning and LLM knowledge,
but is not assumed to know the paper's subfield, its cited methods, or its implementation
conventions.

## Default Reader

Assume the reader understands:

- tensors, matrix multiplication, gradients, and optimization at an introductory level
- MLP/FFN, softmax, cross-entropy, and basic supervised learning
- the high-level Transformer flow: tokens, embeddings, attention, FFN, residual connections
- the basic difference between training and inference
- the high-level purpose of language-model pretraining

Do not assume the reader already understands:

- specialized architectures such as MoE, Q-Former, Perceiver, state-space models, or latent
  attention
- routing, dispatch/combine, expert parallelism, capacity factors, or load balancing
- RLHF, DPO, PPO, KL penalties, reward models, or advantage estimation
- RAG indexes, dense retrieval, reranking, query rewriting, or agent planning
- mechanistic interpretability, causal tracing, activation steering, model editing, or SAE
- multimodal connectors, contrastive learning variants, or paper-specific objectives
- a cited baseline's detailed architecture or why the paper compares against it

When uncertain, prefer one short teaching bridge over silently assuming subfield knowledge.

## Build A Concept Dependency Map

Before writing, create an internal dependency map for the paper's core contribution:

```text
paper contribution
-> mechanisms required to understand it
-> prerequisite concepts required to understand each mechanism
-> which prerequisites exceed the default reader model
-> where each missing prerequisite must be bridged in the report
```

For example:

```text
fine-grained MoE experts
-> token-choice routing and gated expert aggregation
-> ordinary Transformer FFN and why MoE replaces it
-> bridge FFN -> MoE -> router before explaining the proposed change
```

The map is an internal writing tool, not a required standalone report section.

## Just-In-Time Teaching Bridge

Insert a background bridge immediately before the first mechanism that depends on it. Keep it
short enough to preserve the paper's main thread, but complete enough to remove the logical jump.

A good bridge answers:

1. What familiar component or problem are we starting from?
2. How does the conventional approach work?
3. Why is that insufficient in the setting of this paper?
4. What exact part does the paper change?

Example:

```markdown
普通 Transformer 中，每个 token 都经过同一个 FFN。MoE 将这个 FFN 替换为多个
独立 FFN，但若每个 token 都运行全部专家，计算量会随专家数增长。因此需要 Router
为每个 token 选择少量专家。DeepSeekMoE 改变的不是这一基本稀疏路由原则，而是专家的
粒度以及共享知识由谁承担。
```

Do not create a long standalone background chapter by default. Teach prerequisites where the
reader needs them.

## Teaching Unit For A Critical Mechanism

For each understanding-critical mechanism, build a coherent teaching unit:

1. **Starting point**: the familiar or conventional method.
2. **Problem**: the concrete failure or limitation.
3. **Paper's change**: exactly what is added, removed, or rearranged.
4. **Operational flow**: inputs, intermediate states, decisions, outputs, and consumers.
5. **Exact computation**: formulas, axes, masks, selection, aggregation, and gradients.
6. **Concrete walkthrough**: one token/sample/batch, preferably with a small explanatory numeric
   example for the hardest operation.
7. **Why it works**: the causal intuition connecting the change to the claimed benefit.
8. **Boundary**: costs, assumptions, omissions, and failure cases.

Do not scatter these answers across distant sections when they can be taught as one connected
unit.

## Explanatory Examples

Use small, clearly labeled explanatory examples when formulas and shapes remain abstract. The
example may use invented values, but must say `解释性例子` and must not be presented as a paper
result.

Example:

```text
解释性例子：
某个 token 对 4 个专家的 logits 为 [1.2, 0.3, 2.1, -0.4]。
softmax 后约为 [0.25, 0.10, 0.59, 0.06]。
top-2 选择 Expert 3 和 Expert 1，路由输出是两位专家输出的门控加权和。
```

The example should illuminate the actual mechanism, not merely decorate the report.

## Knowledge Boundary

Teach enough background to understand the paper, not the entire subfield.

- Compress prerequisites already inside the default reader model.
- Expand prerequisites that directly affect the paper's architecture, formula, experiment, or
  claim.
- Omit historical detail and unrelated variants unless they resolve a likely misunderstanding.
- Link a background concept to the paper immediately after explaining it.

## Comprehension Audit

Before delivery, simulate a reader with only the default knowledge. For every critical mechanism,
verify that the report lets the reader answer:

- What existed before this paper?
- Why was it insufficient?
- What did the paper change?
- How does one input move through the change?
- How is the output calculated?
- How does the component learn?
- Why should the change help?
- What remains unclear because the paper or sources omit it?

If the explanation requires an unstated subfield concept to answer any question, add a teaching
bridge before delivery.
