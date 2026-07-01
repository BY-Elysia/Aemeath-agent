# Mechanism Depth

Use this guide for every understanding-critical mechanism in a paper. Examples include routing,
retrieval, attention, masking, sampling, memory updates, optimization objectives, decoding,
interventions, data filtering, and evaluation procedures.

The report is not complete when it merely names the steps. It must expose enough of the
mechanism that a technical reader could reproduce the logical computation without reopening the
paper.

## Identify The Critical Mechanisms

Before writing, list the smallest set of mechanisms that carry the paper's contribution, usually
three to seven. A mechanism is understanding-critical when removing its details would prevent the
reader from answering one of these questions:

- What exact values are computed?
- How does the method choose, route, retrieve, mask, rank, or update something?
- How does one sample or batch move through the new method?
- Which parameters learn from which signal?
- How does the proposed method differ operationally from the baseline?

Spend most of the report's technical depth on these mechanisms. Background components may be
shorter.

## Required Mechanism Record

For each critical mechanism, explain all applicable items:

1. **Conventional starting point**: what the default reader already knows or must be taught before
   this mechanism, and how the conventional method works.
2. **Role and change**: the problem it solves, its position in the complete architecture, and the
   exact difference introduced by the paper.
3. **Inputs and state**: tensors, candidates, parameters, caches, external state, and shapes.
4. **Exact computation**: logits/scores, normalization, masks, reductions, selection, sampling,
   aggregation, and output construction in execution order.
5. **Control decision**: top-k, threshold, argmax, routing, retrieval, branching, stopping, or
   update rule, including what is selected and what is discarded.
6. **Outputs and consumers**: output shape and the next component that uses it.
7. **Learning path**: supervision, loss contribution, trainable/frozen parameters, differentiable
   and non-differentiable operations, and gradient/update path.
8. **One concrete trace**: follow one token, sample, query, candidate set, or batch through the
   mechanism using shapes and symbolic/example values. Clearly mark invented values as an
   explanatory example, not a paper result.
9. **Expanded pseudocode**: show the mechanism's internal operations. Do not replace it with a
   function bearing the mechanism's name.
10. **Why the change should help**: connect the operational change to the paper's claimed benefit,
    rather than repeating the claim.
11. **Boundary**: omitted implementation details, assumptions, failure cases, or costs.

If the paper does not state an applicable item, write `原文未明确说明`. Do not silently skip it or
invent it.

## Routing And Selection Minimum Standard

For a router, selector, retriever, reranker, sparse gate, or top-k module, the report must answer:

- What are the candidates and how many are there?
- Which input representation is scored against which candidate representation?
- What is the raw logit formula before normalization?
- Is the score a dot product, cosine similarity, MLP output, distance, probability, or another
  quantity?
- Along which axis is softmax or other normalization applied?
- Is top-k applied before or after normalization? Are selected weights renormalized afterward?
- What happens to unselected candidates?
- How are selected inputs dispatched and outputs combined?
- Is there capacity limiting, token dropping, noise, tie-breaking, or load balancing?
- Does gradient pass through the score, selected gate values, and selection operation?
- Which auxiliary losses modify the router?

A sentence such as “the router computes affinity scores and selects top-k experts” is a heading,
not an explanation.

For token-choice MoE routing, a complete explanatory reconstruction normally resembles:

```python
def route_one_token(u, expert_centroids, expert_w1, expert_w2, k):
    # u: [d]; expert_centroids: [N, d]
    logits = expert_centroids @ u               # [N], raw token-to-expert scores
    probs = softmax(logits, dim="experts")      # [N]
    gate, expert_ids = topk(probs, k=k)         # each [k]

    selected_outputs = []
    for expert_id in expert_ids:
        hidden = activation(expert_w1[expert_id] @ u)
        selected_outputs.append(expert_w2[expert_id] @ hidden)

    routed = sum(g * y for g, y in zip(gate, selected_outputs))
    return routed, probs, expert_ids
```

This is only a structural example. The report must adapt it to the paper and state whether the
paper renormalizes selected gates, imposes capacity limits, or specifies dispatch details.

## Formula-To-Algorithm Bridge

Do not let equations and pseudocode become separate descriptions. For each critical equation:

- point to the pseudocode line that implements it
- explain each reduction and axis
- show the intermediate tensor shapes
- explain how its output changes the next computation

Conversely, every nonstandard pseudocode line should be grounded in a paper equation, algorithm,
figure, prose statement, appendix, or official implementation. Mark explanatory reconstruction
and official implementation details distinctly.

## Concrete Trace Standard

A useful trace includes all important state transitions, for example:

```text
one token state u: [d]
-> router logits against N routed experts: [N]
-> softmax over expert axis: [N]
-> top-k selected IDs and gate values: [k], [k]
-> k expert outputs: [k, d]
-> gate-weighted sum: [d]
-> add shared-expert output and residual: [d]
```

Shapes alone are not enough when the calculation remains abstract. Add a tiny symbolic or
invented-number example for the hardest operation when it materially improves understanding,
and explicitly label it `解释性例子`.

Before the trace, make sure the default reader understands what the mechanism is replacing or
extending. A worked route through an unexplained architecture is still hard to follow.

## Depth Failure Conditions

The mechanism is still too shallow if any of these are true:

- prose only says what a named module does, without how it computes
- a critical formula is followed only by symbol definitions or intuition
- pseudocode calls an undefined paper-specific function
- top-k/routing/retrieval is described without raw scores, normalization axis, and downstream use
- a loss is described without targets, reductions, optimization direction, and affected parameters
- no complete pass shows how the mechanism participates in training or inference
- the explanation begins from a specialized mechanism without bridging the conventional method
- the report states that the paper improves a baseline without explaining the operational
  difference that causes the improvement
- the explanation cannot answer “how would I implement the next line?”

Resolve these failures before writing the conclusion.
