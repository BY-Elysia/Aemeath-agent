# Mathematical Typography

Use this guide whenever a report contains mathematical variables, symbolic expressions, tensor
shapes, equations, or paper notation. Correct notation is part of the explanation: a variable
rendered as plain text is harder to read and may be mistaken for a code identifier or typo.

## Markdown Math Delimiters

- Use `$...$` for inline mathematical notation in prose, bullets, headings, and Markdown tables.
- Use `$$...$$` for display equations.
- Keep Chinese or English prose, punctuation, and quantifier words outside the delimiters.
- Use backticks only for literal code identifiers, CLI commands, filenames, or pseudocode.
- Do not put math delimiters inside fenced code blocks; code blocks should use valid code syntax.
- Prefer one delimiter style throughout the report. Do not mix plain notation, `$...$`, and
  `\(...\)` for the same class of symbols.

Correct:

```markdown
$K_s$ 个共享专家始终激活。

从 $mN-K_s$ 个路由专家中选择得分最高的 $mK-K_s$ 个。

门控权重 $g_{i,t}$ 乘以专家输出 $\operatorname{FFN}_i(u_t^l)$。
```

Incorrect:

```markdown
K_s 个共享专家始终激活。
mN-K_s 个候选中选择 mK-K_s 个。
`g_{i,t}` 乘以 FFN_i(u_t^l)。
```

The incorrect version renders paper notation as ordinary text or code.

## Explain Compact Notation

Typesetting alone is insufficient when notation is compact or easy to misread. At first use,
explain how a derived quantity is constructed and what it counts.

For example:

```markdown
路由专家总数为 $mN-K_s = m\times N-K_s$：将原来的 $N$ 个专家分别细分为
$m$ 个，得到 $mN$ 个细粒度专家，再扣除其中固定作为共享专家的 $K_s$ 个。
```

After defining it once, later prose may use `$mN-K_s$` directly. When several long expressions
recur, introduce a clearly labeled explanatory alias only if it improves readability, for example
`$N_r \coloneqq mN-K_s$（报告中记作路由专家总数）`. Do not imply that a report-defined alias
was introduced by the paper.

## What Belongs In Math

Put these in inline or display math:

- paper variables and indexed symbols: `$N$`, `$K_s$`, `$g_{i,t}$`, `$\alpha_1$`
- arithmetic and relations: `$mN-K_s$`, `$K=2$`, `$i\in\mathcal{E}$`
- tensor shapes when used mathematically: `$[B,T,d]$`, `$\mathbb{R}^{T\times d}$`
- symbolic function calls from equations: `$\operatorname{softmax}(z)$`,
  `$\operatorname{FFN}_i(u_t^l)$`

Keep these as prose or code:

- technical names: MoE, Router, softmax, top-k, FFN
- literal implementation identifiers: `router_logits`, `topk_indices`, `hidden_states`
- literal code shapes inside pseudocode comments: `[B, T, d]`

Do not write a hybrid such as `top-(mK-K_s)`. Prefer natural prose:

```markdown
选择得分最高的 $mK-K_s$ 个路由专家
```

## Readability Audit

Before delivery:

1. Search prose, headings, bullets, and Markdown tables for bare `_`, `^`, equality, and arithmetic
   expressions that represent paper notation.
2. Confirm each mathematical expression is inside `$...$` or `$$...$$`.
3. Confirm code identifiers are inside backticks or code fences, not math delimiters.
4. Confirm every compact derived quantity is explained in words at first use.
5. Preview the Markdown and inspect subscripts, superscripts, Greek letters, matrices, and equations.

Fail the report if readers see raw strings such as `K_s`, `g_{i,t}`, `mN-K_s`, or `alpha_1` in
prose instead of rendered notation.
