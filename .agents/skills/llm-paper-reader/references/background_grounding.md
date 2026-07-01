# Background Grounding

Use this guide when the paper assumes prerequisite knowledge, leaves a baseline unexplained, or
omits implementation details needed for a beginner-accessible explanation.

## Source Layers

Use sources in this order:

1. **Current paper**: authoritative for its contribution, claims, equations, experiments, and
   stated design.
2. **Paper appendix and supplementary material**: authoritative for omitted details supplied by
   the authors.
3. **Official implementation or project page**: useful for operational details; distinguish code
   behavior from the paper's mathematical statement.
4. **Cited original paper for a prerequisite or baseline**: use to explain mechanisms that the
   current paper assumes are known.
5. **Primary-source technical documentation or standard textbook knowledge**: use only for the
   minimum bridge required by the default reader.

Prefer primary sources. Do not rely on unsourced summaries when the original paper, official code,
or official documentation is available.

## When To Add External Background

Add a background bridge when:

- a core mechanism depends on an undefined subfield concept
- the paper says “following X” or “we use standard X” without explaining X
- a baseline difference is central to the paper's contribution
- an equation cannot be understood without a conventional objective or algorithm
- official code resolves an implementation choice that materially affects understanding

Do not add external background merely because it is related.

## Attribution In The Report

Keep source layers distinct in natural prose:

- `本文提出……` for the current paper's contribution
- `为了理解这一设计，先补充传统 MoE 的基本工作方式……` for standard background
- `论文沿用 GShard 的 token-choice routing；该机制中……` for a cited prerequisite
- `论文正文未展开，官方实现中……` for official-code details
- `下面的数值仅用于解释计算过程，不是论文实验结果` for invented teaching examples

Do not turn the report into an evidence ledger, but never let external knowledge appear to be a
claim or contribution of the current paper.

## Handling Conflicts And Omissions

- If the current paper and official code differ, explain the difference and which one the report
  uses for each statement.
- If a cited method has several variants, explain only the variant the current paper uses or most
  clearly implies.
- If no primary source resolves an implementation detail, write `原文及可用官方资料未明确说明`.
- Do not invent layer order, normalization, negative sampling, hyperparameters, or gradient paths
  to make an explanation feel complete.

## Background Bridge Record

Internally record for each added bridge:

- prerequisite concept
- why the reader needs it
- source layer and source
- minimum facts required
- the report location where it is introduced
- how it connects back to the current paper

This record is internal. The final report should remain a coherent academic explanation.

## Grounding Audit

Before delivery, verify:

- every external fact is either common introductory knowledge or grounded in a primary source
- every current-paper claim remains distinguishable from background explanation
- every official-code detail is labeled as implementation behavior
- every invented teaching example is explicitly labeled
- background material returns to the paper's mechanism instead of becoming a detached tutorial
