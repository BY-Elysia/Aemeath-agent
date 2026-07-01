---
name: llm-paper-reader
description: Use when reading, summarizing, explaining, reviewing, or implementing LLM and large-model papers, including architecture, training, inference, alignment, RAG, agents, multimodal, benchmark, and systems papers. Produces beginner-accessible but technically rigorous Chinese academic Markdown reports for readers with basic LLM and deep-learning knowledge, with prerequisite bridges, architecture and process explanations, calculation-level formulas, expanded pseudocode, relevant cropped original figures/tables, and grounded limitations and future work.
---

# LLM Paper Reader

## Goal

Read LLM-field papers and produce a formal academic explanation report that a reader with basic LLM and deep-learning knowledge can understand without already knowing the paper's subfield. Avoid generic summaries and translation-like paraphrases. Explain the paper's problem setting, prerequisite concepts, complete conceptual architecture, method logic, formulas, algorithms or pseudocode, experiments, author-stated limitations and future work, and implementation implications.

The default deliverable is a polished Chinese Markdown report, usually named `report.md`, not a collection of notes. Text extraction, figure extraction, and evidence mapping are internal preparation steps.

## When Starting

1. Prefer the original source: local PDF, arXiv HTML/PDF, paper website, official code, or provided text.
2. Extract metadata: title, authors, date or venue if available, source path or URL, and paper type.
3. If the source is a PDF, run or adapt:
   - `scripts/extract_paper_text.py paper.pdf --out paper_text.md`
   - `scripts/extract_figures.py paper.pdf --out-dir figures --metadata figures/metadata.json`
   - `scripts/extract_tables.py paper.pdf --out-dir tables --metadata tables/metadata.json`
4. When using original figures or tables, use cropped assets that contain only the figure/table body and necessary legend. Never embed full-page screenshots in the final report; generate a grounded replacement or omit the image if no usable crop can be produced.
5. Build an internal evidence map before final writing. Track section, page, figure, table, equation, algorithm, and appendix anchors for grounding, but do not expose the evidence map as a final report section.
6. Load only the needed reference files:
   - Use `references/output_templates.md` for the final report structure.
   - Use `references/architecture_checklist.md` for architecture-heavy papers.
   - Use `references/reader_model_and_pedagogy.md` for every report to model the default reader, build prerequisite bridges, and run the comprehension audit.
   - Use `references/background_grounding.md` when the paper assumes prerequisite knowledge, cites an unexplained baseline, or requires official code/cited work to teach clearly.
   - Use `references/mechanism_depth.md` for every understanding-critical mechanism, especially routing, retrieval, attention, masking, sampling, memory, decoding, and optimization.
   - Use `references/formula_explanation.md` whenever the paper contains equations, losses, algorithms, or mathematical notation.
   - Use `references/math_typography.md` whenever the report contains mathematical variables, expressions, equations, or tensor shapes.
   - Use `references/pseudocode_guide.md` whenever the report needs to explain a model forward pass, training step, inference algorithm, retrieval/routing process, or update rule.
   - Use `references/terminology_guide.md` when the paper introduces named terms, modules, metrics, datasets, or objectives.
   - Use `references/experiment_checklist.md` when analyzing experiments, baselines, ablations, or metrics.
   - Use `references/limitations_future_work.md` when extracting author-stated limitations, failure cases, risks, future work, open questions, or report-level boundary analysis.
   - Use `references/visual_policy.md` when extracting original figures or generating explanatory diagrams.

## Paper Type

Classify the paper as one or more of:

- model architecture
- training method
- inference or decoding method
- alignment, RLHF, preference optimization, or safety
- RAG, agent, memory, tool use, or data construction
- multimodal LLM
- benchmark or evaluation
- systems, serving, compression, or efficiency
- analysis, interpretability, or survey

Use the classification to decide which sections need the deepest reading.

## Required Reading Workflow

1. Skim title, abstract, introduction, and conclusion to identify the problem and claimed contributions.
2. Read the method section deeply and extract modules, data flow, objectives, algorithms, and inference-time behavior.
3. Build an internal concept dependency map from the paper's contribution to its mechanisms and prerequisites. Compare each prerequisite against the default reader model in `references/reader_model_and_pedagogy.md`.
4. For every prerequisite gap, locate the minimum grounded background from the current paper, appendix, official code, cited original work, or primary-source documentation. Use `references/background_grounding.md`.
5. Inspect figures, tables, equations, and algorithms before writing conclusions.
6. Verify every understanding-critical equation against the rendered PDF, paper source, or official code. PDF text extraction often corrupts parentheses, superscripts, subscripts, and operator scope; do not explain an unverified extracted equation.
7. Read experiments for datasets, baselines, metrics, main results, ablations, and failure cases.
8. Inspect limitations, discussion, conclusion, failure cases, broader impact, ethical considerations, and appendix notes. Extract the authors' explicitly stated limitations and future directions, even when they are scattered outside a dedicated section.
9. Distinguish current-paper claims, cited/background knowledge, official-code behavior, author-stated limitations, experiment-supported boundaries, and your own cautious analysis.
10. Identify the three to seven understanding-critical mechanisms. For each one, build a teaching unit and mechanism record containing conventional starting point, prerequisite bridge, paper change, exact computation, inputs/outputs and shapes, control or selection rule, learning path, one concrete trace, and expanded pseudocode.
11. Audit formulas and pseudocode together. Expand or define every understanding-critical call and verify that formulas, tensor axes, reductions, shapes, masks, frozen/trainable state, selection rules, and gradient/update paths agree.
12. Produce a polished Chinese Markdown report using the output template. Preserve the paper's logical progression, but organize explanations according to reader dependencies rather than mechanically mirroring subsection headings.
13. Run the final comprehension, depth, grounding, mathematical-typography, and visual audit. Do not deliver while the explanation assumes unstated subfield knowledge, a critical mechanism remains a named black box, an important formula cannot be followed as a calculation, mathematical notation appears as raw text in prose, or a final-report image is an uncropped full page.

## Evidence Rules

- Use evidence anchors internally to avoid hallucination. In the final report, cite paper locations naturally only where it helps academic reading, such as `Sec. 3`, `Fig. 2`, `Table 4`, `Eq. 1`, or appendix references.
- Use short original-text quotes only when they support a claim or define a term.
- Distinguish author claims, experimental support, and your own synthesis in prose; do not turn this distinction into a mechanical evidence-index table unless the user asks.
- If the paper omits a detail, write `原文未明确说明`.
- Do not invent modules, datasets, baselines, hyperparameters, metrics, equations, or results.
- Do not present external background knowledge as if it came from the paper.
- Use external background when required to bridge prerequisite gaps, but prefer primary sources and state naturally whether a fact comes from standard background, cited work, or official implementation.
- Label invented numeric walkthroughs as `解释性例子`; never present them as paper results.
- Do not present report-level limitation analysis or suggested future work as if the authors stated it.
- Do not include a final bookkeeping section that lists evidence anchors unless explicitly requested.

## Architecture Requirements

Before deep-diving into details, establish the complete conceptual architecture of the paper: what problem enters the system, what objects or modules the paper operates on, how information flows, what objective or intervention changes, and what output or conclusion is produced.

If the paper has a nontrivial training loop, inference loop, routing algorithm, retrieval process, attention mask, optimizer update, or evaluation procedure, include concise pseudocode or code-like blocks that show one complete pass through the method. Recursively expand paper-specific functions until the novel mechanism is visible; do not hide the core contribution behind calls such as `proposed_module(...)`, `qformer(...)`, `router(...)`, or `compute_paper_loss(...)`.

For each understanding-critical mechanism, the report must expose its exact execution path rather than only its purpose. At minimum, cover inputs/state, raw computation, normalization and reduction axes, control or selection decision, outputs and consumers, learning/gradient path, one concrete token/sample/batch trace, and expanded pseudocode. If an item is not stated, say `原文未明确说明`.

For architecture or method papers, explicitly cover:

- input and output format
- backbone or base model
- newly introduced modules
- attention, routing, retrieval, memory, tool, or multimodal interfaces
- training objectives and stages
- inference-time behavior
- computational cost, latency, or hardware assumptions if stated
- structural differences from the baseline

Use `references/architecture_checklist.md` for a complete inspection list.
Use `references/mechanism_depth.md` for the minimum acceptable depth of each critical mechanism.

## Explanation Quality Requirements

- Write for the default reader defined in `references/reader_model_and_pedagogy.md`: basic LLM and deep-learning knowledge, but no assumed subfield expertise.
- Do not translate or paraphrase paragraph by paragraph.
- Do not merely restate the paper's outline.
- First build the full architecture or conceptual map, then explain local pieces inside that map.
- Before a mechanism uses specialized prerequisite knowledge, insert a just-in-time teaching bridge: conventional starting point, how it works, why it is insufficient here, and what the paper changes.
- For each important mechanism, explain: what it is, why it is needed, how it works, what it consumes, what it produces, and what can go wrong.
- For every paper-specific module invoked in prose or pseudocode, define its function contract: inputs, outputs, shapes when available, internal operations, masks/selection rules, trainable or frozen state, and gradient/update path.
- A phrase such as “compute similarity/affinity and select top-k” is not a sufficient explanation. Show the compared objects, raw score equation, normalization axis, selection timing, treatment of discarded candidates, dispatch/combine or downstream use, and learning signal.
- Use one concrete trace for each difficult core mechanism. Follow one token, sample, query, candidate set, or batch through the actual intermediate states and shapes; use clearly labeled explanatory values only when helpful.
- Use small numerical walkthroughs for the hardest score, normalization, selection, loss, or update computations when symbols alone are unlikely to be intuitive.
- Background explanation must reconnect immediately to the paper's mechanism; do not create a detached textbook chapter.
- Prefer explanatory prose over long bullet lists. Use bullets only for dense comparisons or implementation details.
- When the paper is a survey, synthesize the field architecture: object layer, method layer, intervention layer, application layer, and evaluation layer.

## Terminology Requirements

For paper-specific terms, explain them when they first appear in the paper's logical flow. Do not create a standalone terminology chapter by default.

- original term
- Chinese explanation
- paper-specific meaning
- why it matters
- first definition or key occurrence anchor
- prerequisite concept the default reader needs before the term
- difference from the closest familiar concept or conventional baseline

Use `references/terminology_guide.md` for the detailed standard.

## Formula Requirements

For every important formula, explain it where it appears in the method flow. Include:

- a notation-faithful equation verified against the rendered paper, source, or official code rather than trusted blindly from extracted text
- what the formula computes
- every symbol's meaning, including dimensions when available
- the calculation steps in plain language
- implementation-level details needed to reproduce the computation, such as normalization, softmax axis, masking, positive/negative samples, averaging, max/top-k selection, or logits
- why this computation is needed
- how the formula connects to the paper's architecture, loss, algorithm, or experiment
- what assumption or limitation the formula implies
- the pseudocode line or algorithmic step that realizes it
- a small worked or symbolic trace when the operator sequence remains difficult to follow
- a conceptual-layer explanation before the calculation: what familiar problem creates the need for this quantity and what behavior it controls

Do not place formulas in a standalone formula chapter by default. Use `references/formula_explanation.md` for the detailed standard.

## Mathematical Typography Requirements

- Use `$...$` for inline paper variables and symbolic expressions in prose, bullets, headings, and Markdown tables; use `$$...$$` for display equations.
- Never leave paper notation such as `K_s`, `g_{i,t}`, `mN-K_s`, or `alpha_1` as raw text outside code blocks.
- Use backticks for literal implementation identifiers such as `router_logits`, not for mathematical notation.
- Keep prose and quantifier words outside math delimiters: write `$K_s$ 个共享专家`, not `$K_s 个共享专家$`.
- At first use, unpack compact expressions in words and arithmetic. For example, explain `$mN-K_s = m\times N-K_s$` as the fine-grained expert total minus shared experts.
- Avoid hybrid notation such as `top-(mK-K_s)`; write natural prose such as `选择得分最高的 $mK-K_s$ 个路由专家`.
- Preview the final Markdown and verify subscripts, superscripts, Greek letters, matrices, and inline expressions render correctly.

Use `references/math_typography.md` for the complete standard.

## Visual Requirements

Always check whether the paper contains useful figures and tables, but use visuals as reading aids inside the relevant academic sections, not as the organizing center of the report.

Priority order:

1. Use original paper figures and result tables when available.
2. Prefer architecture diagrams, method flowcharts, training pipelines, inference pipelines, data construction diagrams, system diagrams, evaluation setup diagrams, main result tables, and ablation tables.
3. Embed selected figures/tables near the section where they clarify the architecture, method, process, or experiment.
4. If no clear original diagram exists, create a grounded explanatory diagram when an image generation tool is available.
5. If no image generation tool is available, output a diagram prompt generated from paper evidence.

Generated diagrams must be clearly captioned as `根据论文内容绘制的解释性示意图`. They must not contain unsupported boxes, arrows, stages, datasets, modules, or claims.

Never embed an asset marked as a full-page fallback or page-render candidate in the final report. Crop it to the visual body first, generate a clearer grounded diagram, or omit it. A figure that cannot be read at normal Markdown preview width is not useful evidence.

Use `references/visual_policy.md` and, when useful:

```bash
scripts/build_diagram_prompt.py evidence.md --diagram-type architecture --out diagram_prompt.md
```

For tables, run or adapt:

```bash
scripts/extract_tables.py paper.pdf --out-dir tables --metadata tables/metadata.json
```

Use cropped table images for main results and important ablations, then explain what claim the table supports in prose. Do not replace experimental analysis with a table dump.

## Output Defaults

- Language: Chinese by default, preserving English technical terms when more precise.
- Format: Markdown by default.
- Create `report.md` by default when working in a filesystem workspace.
- Include original figures or generated diagrams inline where they help explain the paper.
- Include cropped original result/ablation tables where they materially support the paper's claims.
- Do not include raw extraction logs, figure metadata dumps, or evidence-index tables in the final report unless requested.
- Do not create standalone terminology, formula-analysis, or figure-reading sections by default. Integrate terminology, formulas, algorithms, and figures into the corresponding conceptual section.
- Avoid meta-report phrasing about the report's writing choices. Captions should directly explain the paper content.
- Avoid reports that read like Chinese translations of the paper. The report should teach the paper's internal logic.
- Do not assume that a mechanism is understandable merely because the paper omits its background. Fill prerequisite gaps for the default reader using grounded teaching bridges.
- Keep the report concrete: architecture, terminology, evidence, experiments, and limitations should be more detailed than the high-level summary.
- Include limitations and future work explicitly stated by the paper. If the paper does not state a future direction, write `原文未明确提出后续研究方向` instead of inventing one.
- Use code blocks for key flows when they improve understanding: training steps, inference steps, attention masks, loss computation, data construction, retrieval/routing, or evaluation.
- Pseudocode must expose the paper's important internals. Standard operations may remain black boxes, but novel or understanding-critical functions must be defined or expanded nearby.
- Before delivery, apply the depth failure conditions in `references/mechanism_depth.md`: critical mechanisms must be calculation-level, formulas must connect to algorithms, and pseudocode must not conceal the contribution.
- Before delivery, apply the comprehension audit in `references/reader_model_and_pedagogy.md` and the source-boundary audit in `references/background_grounding.md`.
- When available, run `scripts/audit_report.py report.md --figures-metadata figures/metadata.json --tables-metadata tables/metadata.json`; resolve all errors, including bare mathematical notation, and review warnings rather than treating the script as a substitute for semantic audit.
