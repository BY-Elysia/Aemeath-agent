# Output Templates

Use this as the default Chinese academic report structure. The report should teach the paper's internal logic. It must not read like a Chinese translation, paragraph-by-paragraph paraphrase, or mechanical reproduction of the paper's subsection headings.

Do not include raw evidence indexes, extraction logs, figure metadata tables, standalone terminology chapters, standalone formula chapters, or figure-by-figure reading sections unless the user explicitly asks for them.

The default reader understands basic LLMs and deep learning, but not the paper's subfield. The
report must provide just-in-time prerequisite bridges instead of inheriting the paper's unstated
assumptions.

When the method contains a nontrivial training, inference, retrieval, routing, masking, or evaluation process, include pseudocode or code-like blocks that let the reader follow one complete pass. These blocks should teach the paper; they are not implementation guarantees unless the paper provides official code. Do not hide the central mechanism behind an undefined paper-specific function.

## 正式论文讲解报告

### 标题区

```markdown
# 论文讲解：<paper title>

- 论文：<title>
- 作者：<authors>
- 发表信息：<venue/date/arXiv if available>
- 主题领域：<LLM architecture/training/alignment/RAG/etc.>
- 阅读定位：<一句话说明这篇论文适合解决什么问题或理解什么方向>
```

### 1. 导读：这篇论文到底解决什么

用 2-4 段讲清楚：

- 论文面对的核心矛盾
- 旧方法为什么不够
- 论文真正提出的思想或框架
- 读者应抓住的主线
- 为理解主线需要补齐的两三个关键前置概念，以及它们和本文的关系

要求：这是讲解开场，不是 abstract 翻译。

### 2. 全局架构：先搭起完整理解框架

这一节必须先于局部细节。目标是让读者先知道整篇论文的“骨架”。

根据论文类型建立一种全局架构：

- 模型论文：输入 -> 编码/模块 -> 训练目标 -> 推理过程 -> 输出
- 训练论文：数据 -> 模型 -> loss/objective -> optimization -> evaluation
- RAG/agent 论文：query -> retrieval/tool/memory -> planner/controller -> generator -> feedback
- alignment 论文：preference/safety data -> reward/preference model -> optimization/intervention -> behavior change
- survey 论文：研究对象层 -> 方法层 -> 干预层 -> 应用层 -> 评估层
- benchmark 论文：任务定义 -> 数据构造 -> 指标 -> baseline -> 分析结论

在这里可以使用原文总览图或生成一张解释性架构图。图注应直接说明图中机制，不解释为什么插入图片。

从读者已经熟悉的普通 Transformer、标准训练流程或常规推理流程出发，再指出本文在哪个
位置替换、增加或重排了组件。不能直接从论文专有模块开始画架构。

### 3. 架构内部的关键部件

围绕全局架构逐块解释，而不是照抄原文小标题。

每个部件都要回答：

- 读者需要先知道什么；传统方法如何工作
- 它在全局架构中的位置
- 它解决什么子问题
- 它相对传统方法具体改变了什么
- 它接收什么输入
- 它产生什么输出
- 它与前后部件如何连接
- 它为什么是论文贡献的一部分

先识别三到七个承载论文贡献的理解关键机制。对每个关键机制，必须讲清精确计算、
控制/选择规则、输入输出与 shape、学习或梯度路径、一个具体样本 trace，以及展开后的
伪代码。只写“计算分数并选择 top-k”或“通过该模块获得表示”不算解释完成。

术语在这里自然解释。例如第一次出现 `residual stream`、`router`、`preference model`、`SAE feature` 时，直接在上下文中说明其中文含义、本文具体含义和作用。

若术语依赖论文未解释的子领域知识，先插入最短够用的背景桥接，并在讲完后立即回到本文。
不要因为论文作者默认读者知道，就把同样的跳步保留在报告中。

### 4. 关键机制与公式逐步解析

不要单独罗列公式。选择对理解方法最关键的公式，把它们放在对应机制下面讲。公式解释必须达到“能照着算一遍”的粒度。

关键公式必须先对照 PDF 版面、论文源码或官方代码核对括号、上下标、转置、求和范围和
算子作用域。不能直接信任 PDF 文本抽取结果。

正文、列表、标题和 Markdown 表格里的数学变量也必须正确渲染。使用 `$K_s$`、
`$g_{i,t}$`、`$mN-K_s$`，不能写成裸文本 `K_s`、`g_{i,t}`、`mN-K_s`。紧凑表达式首次
出现时要展开其含义，例如说明 `$mN-K_s = m\times N-K_s$` 表示细分后的专家总数减去
共享专家数。

每个公式使用这个讲法：

```markdown
普通/传统方法先解决 <familiar problem>。本文还需要控制 <new behavior>，所以这里要
计算 <what>。

$$
...
$$

这个式子可以分三步看：
第一，...
第二，...
第三，...

其中，<symbol> 表示 ...，形状/范围是 ...；<symbol> 表示 ...。
如果涉及 similarity、softmax、attention、loss、top-k、routing、negative sampling 或 logits，说明归一化、比较对象、softmax 维度、正负样本来源、聚合方式和优化方向。
这个公式的作用是 ...。它和前面的 <module/objective> 的关系是 ...。

解释性例子：<用小型数值或符号走一遍最难的运算；明确它不是论文实验结果>
```

必须解释：

- 每个重要符号是什么意思
- 这个量是怎么一步步算出来的
- 为什么要这么算
- 这个公式在训练、推理、定位、干预或评估中的作用
- 公式隐含的假设或局限
- 公式对应哪一行伪代码或哪个执行步骤，结果接下来被谁使用
- 对最难的公式给出一个小型符号推演或明确标注为解释用途的数值例子

如果原文公式很多，可以只深讲核心公式，次要公式简要解释，但不能跳过影响理解的目标函数、更新规则、注意力计算、loss、reward、routing、retrieval score 或 evaluation metric。

### 5. 方法如何运行：从输入到输出走一遍

用一条具体流程把前面部件串起来。不要停留在概念层。

说明：

- 给定一个输入，第一步发生什么
- 中间状态如何被计算或更新
- 哪些模块参与训练，哪些只在推理时使用
- 最终输出如何产生
- 每一步相对普通 Transformer、传统 baseline 或常规训练流程发生了什么变化
- 如果是 survey，则用一个典型应用例子串起 object localization -> intervention -> evaluation

这一节应让读者能复述“方法实际怎么跑”。

伪代码通常分三层展开：

1. 端到端流程：一个输入或 batch 如何到达输出/loss。
2. 核心模块 forward：论文新模块内部如何处理输入。
3. objective/update：分数、正负样本、loss、梯度或参数更新如何计算。

伪代码必须使用论文中的真实对象、模块、mask、loss、负样本、prompt、retrieval candidates 或更新对象。凡是论文核心模块或关键计算，例如 `qformer(...)`、`router(...)`、`retrieve(...)`、`compute_similarity(...)`，都必须在附近继续展开或给出完整函数契约，不能只写一个函数名。

对于 routing、retrieval、top-k、sampling 或其他选择机制，必须展示候选集合、原始
logits/score、归一化轴、选择发生的位置、未选中项如何处理、选中项如何参与后续计算，
以及相关 loss 如何训练选择器。再用一个 token/query/sample 走完整条路径。

每个关键函数应让读者知道：输入/输出是什么、shape 是什么、内部按什么顺序计算、哪些 mask/选择规则生效、哪些参数冻结或更新、输出接下来被谁使用。标准操作如 `cross_entropy`、`backward`、`optimizer.step` 可以保留为黑盒。

### 6. 实验与结果：论文如何证明它有效

按证明链条解释实验，而不是只翻译结果表：

- 作者想证明哪些 claim
- 每个实验对应哪个 claim
- 数据集、baseline、指标如何服务于这个 claim
- baseline 的工作方式和它与本文的关键差异；不要只列 baseline 名称
- 主结果说明了什么
- 消融实验排除了哪些替代解释
- 结果没有证明什么

应优先保留主结果表、关键消融表、成本/参数表和能支撑核心 claim 的对比表。表格必须使用裁剪后的原文表格图片，不能用整页截图夹带正文。表格前后必须解释结果逻辑：作者想证明什么、数字怎样支持它、数字没有证明什么。

### 7. 局限、作者展望与适用边界

先提取论文作者自己明确写出的不足和后续方向，再结合前面架构与实验分析适用边界。必须区分：

- 作者明确指出的 limitation、failure、risk 或假设
- 作者明确提出的 future work、planned extension、mitigation 或 open question
- 实验或消融直接显示的能力边界
- 报告基于架构和缺失实验作出的谨慎分析

每个重要不足要讲清它来自哪个模块、数据、假设或实验设置，会在什么场景造成什么影响，以及论文是否提出缓解方案。每个作者展望要说明它准备解决当前方法的哪个问题，需要修改什么组件、数据、训练目标或评估设置。

不要把自己的建议写成作者观点，不要泛泛写“需要更多实验”。如果论文没有明确提出后续研究方向，写 `原文未明确提出后续研究方向`。

### 8. 复现与实现路线

面向想复现或应用论文的人，给出可执行理解：

- 必须准备的数据
- 必须实现的模块
- 必须记录的中间状态
- 训练/推理顺序
- 关键超参数
- 检查结果是否正确的方法
- 最容易踩坑的地方

### 9. 总结：这篇论文真正教会了什么

用 2-4 段收束：

- 论文的真正贡献
- 它改变了你对该方向的哪一点理解
- 方法或框架最有价值的部分
- 它的边界和后续方向

## Integration Rules

- 面向只有基础 LLM/深度学习知识的读者，不默认其掌握论文子领域。
- 写作前建立内部概念依赖图，并在依赖第一次被使用前补齐必要背景。
- 背景桥接放在对应机制附近，不单独堆成教科书章节。
- 明确区分本文贡献、被引工作背景、官方实现细节和报告的解释性例子。
- 先建立完整架构，再解释局部。
- 不要机械模仿原文小标题。
- 不要逐段翻译原文。
- 术语在其所属机制中解释。
- 公式在其所属机制中解释。
- 正文中的数学变量和表达式使用行内数学环境，并在首次出现时解释紧凑符号的含义。
- 图像在对应方法、架构、实验或流程段落中嵌入。
- 最终报告禁止嵌入整页 PDF 渲染候选图；只能使用裁剪后的图表主体或 grounded 生成图。
- 表格在对应实验段落中嵌入，并解释它支持的 claim。
- 伪代码在训练、推理、路由、检索、mask 或评估机制附近嵌入。
- 伪代码递归展开到论文创新点可见为止，不能用未定义函数重新命名关键机制。
- 作者明确提出的不足和展望必须保留，并与报告自己的分析区分。
- 可以保留原文逻辑顺序，但要用讲解逻辑重组小节。

## Style Requirements

- 中文为主，保留必要英文技术术语。
- 正式、清晰、连贯，像学术讲解稿。
- 每一节都要回答“为什么”和“怎么做”，不能只回答“是什么”。
- 对关键机制，优先讲到一次输入或一个 batch 实际如何流动、如何计算、如何更新。
- 交付前逐项检查关键机制；凡是不能回答“下一行代码怎样写、下一个中间量怎样算”的部分，都要继续展开。
- 交付前模拟默认读者闭卷阅读；凡是必须依靠未说明的子领域知识才能理解的部分，都要
  增加背景桥接、传统方法对照或解释性例子。
- 不要写成提示词执行痕迹、证据表、审计清单或流水账。
- 不要使用元话语解释报告写作动作。
- 若论文缺少某个实现细节，写 `原文未明确说明`，不要猜测。
- 交付前预览 Markdown，确认正文中的下标、上标、希腊字母和数学表达式均已正确渲染。
