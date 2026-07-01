# Pseudocode Guide

Use this guide whenever a paper contains a nontrivial model module, training loop, inference algorithm, routing process, retrieval process, memory update, data construction pipeline, or evaluation procedure.

The purpose of pseudocode is to expose how the paper works. Do not hide the paper's core contribution behind an undefined function call.

Before showing paper-specific pseudocode, bridge from the conventional algorithm when the default
reader would not otherwise know what the code replaces or extends. Pseudocode without that
starting point can be executable yet still pedagogically opaque.

## Black-Box Rule

Recursively expand pseudocode until the paper's novel mechanism is visible.

A function may remain unexpanded only when:

- it is a standard operation rather than a paper contribution, such as tokenization, `cross_entropy`, `backward`, or `optimizer.step`
- its exact internals do not affect understanding of the paper
- its relevant behavior has already been defined nearby

Expand or define any paper-specific or understanding-critical call, such as:

- a newly proposed model/module: `qformer`, `router`, `connector`, `adapter`, `resampler`
- a novel scoring or selection function: `compute_similarity`, `retrieve`, `rerank`, `select_experts`
- a novel update: `memory_update`, `policy_update`, `edit_weights`
- a nonstandard training/inference procedure

Bad:

```python
features = proposed_module(inputs)
loss = compute_paper_loss(features)
```

This only renames the unexplained mechanism.

Better:

```python
features = proposed_module_forward(inputs, mask)
loss = paper_loss(features, positives, negatives)
```

Then define `proposed_module_forward` and `paper_loss` nearby.

## Three-Layer Decomposition

For architecture or method papers, usually provide these layers:

1. **End-to-end pass**: show how one sample or batch travels from raw input to output/loss.
2. **Core module forward pass**: expand the paper's novel module and expose its internal operations.
3. **Objective/update pass**: show how scores, targets, losses, sampling, gradients, or parameter updates are computed.

Do not force all three layers when the paper is simple. Do not stop at layer 1 when the core module remains a black box.

For each difficult core mechanism, include a concrete trace after the pseudocode. A reader should
be able to map the trace's intermediate states to specific pseudocode lines and equations.

For the hardest score, selection, or update, prefer a tiny clearly labeled numerical walkthrough
in addition to shapes when that makes the computation materially easier to understand.

## Function Contract

Before or after each important pseudocode function, make these points clear:

- purpose
- inputs and tensor shapes when available
- trainable, frozen, retrieved, cached, or externally supplied state
- internal operations in execution order
- masks, routing rules, sampling rules, or selection conditions
- outputs and tensor shapes
- where the output is consumed
- which parameters receive gradients or updates

Use comments to explain why an operation exists or what information it permits. Avoid comments that merely repeat the code.

## Core Module Example

The following illustrates the required depth for a query-based multimodal connector. Use paper-specific names and include only operations supported by the paper.

```python
def connector_forward(learned_queries, image_tokens, text_tokens, attention_mask):
    # learned_queries: [M, d]; image_tokens: [B, N, d_v]
    # Repeat the same trainable query parameters for every sample.
    query_states = repeat(learned_queries, batch_size=B)  # [B, M, d]
    text_states = embed(text_tokens)                      # [B, L, d]
    hidden = concat(query_states, text_states, dim="sequence")

    for layer_index, block in enumerate(transformer_blocks):
        # The task-specific mask decides whether query/text positions exchange information.
        hidden = block.self_attention(hidden, mask=attention_mask)

        if layer_has_cross_attention(layer_index):
            # Only query positions read frozen visual features.
            hidden[:, :M] = block.cross_attention(
                queries=hidden[:, :M],
                keys=image_tokens,
                values=image_tokens,
            )

        hidden = block.feed_forward(hidden)

    return hidden[:, :M], hidden[:, M:]
```

After this block, explain what `M`, `N`, `L`, `d`, and `d_v` mean; how `attention_mask` changes between objectives; which layers contain cross-attention; and whether the image encoder and connector are updated. If the paper does not state an implementation detail, write `原文未明确说明`.

If attention itself is the paper's contribution, expand its score/mask/softmax computation too. If attention is standard and only its connectivity matters, a formula plus the mask explanation is sufficient.

## Concrete Trace

When the algorithm remains difficult to understand, add a short trace for one sample or one batch:

```text
input shapes
-> intermediate states and shapes
-> candidate/negative selection
-> score or logits
-> loss/output
-> updated parameters
```

Use a concrete example only to clarify the mechanics. Do not invent numeric values, tokens, retrieved items, or predictions and present them as paper results.

## Grounding

- Prefer the paper's algorithm box, equations, appendix, and official code when available.
- State when pseudocode is an explanatory reconstruction rather than official implementation.
- Do not invent layer order, tensor dimensions, loss weights, sampling distributions, or gradient paths.
- If official code and paper prose differ materially, explain the difference.

## Completeness Audit

Before finalizing the report, audit every pseudocode block:

- List the functions it calls.
- Classify each call as standard or paper-specific/understanding-critical.
- Confirm every paper-specific/critical call is expanded nearby or has a complete function contract.
- Confirm tensor shapes, masks, selection rules, frozen/trainable state, and gradient paths agree with the surrounding explanation.
- Confirm the pseudocode and formulas describe the same computation.
- Confirm every critical score/selection path exposes raw values, normalization, selection,
  discarded items, and downstream consumption.
- Confirm each difficult critical mechanism has one token/sample/query/batch trace.
- Confirm the reader knows the conventional starting point and why the paper-specific code differs.
- Confirm invented values in walkthroughs are labeled as explanatory examples, not paper results.
- Remove decorative code blocks that only rename prose without exposing additional mechanics.
- Mark all unsupported implementation details as `原文未明确说明`.
