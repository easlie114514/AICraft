---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/harness_engineering_report.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1783481723480
    ReservedCode2: ""
---
# Harness Engineering：从外层系统到递归自我改进

> 完成日期：2026-07-08 | 作者：AI Research Assistant

当模型智能足够强大时，决定Agent能走多远的不再是模型本身，而是外层Harness系统。**LangChain仅通过改进Harness层（不改模型），就在TerminalBench 2.0上将排名从30名外跃升至第5名，准确率从52.8%提升至66.5%** [(ybuild.ai)](https://ybuild.ai/en/blog/harness-engineering-complete-guide-ai-coding-agents-2026)。**Meta-Harness在TerminalBench-2上自动发现的Harness达到76.4%通过率，超越了人工精心调教的Terminus-KIRA（74.7%）** [(Lee et al. 2026)](https://arxiv.org/abs/2603.28052)。**Darwin Gödel Machine让Agent修改自身Harness代码，在SWE-bench Verified上从20%提升至50%** [(Zhang et al. 2025)](https://arxiv.org/abs/2505.22954)。

然而，当前自我改进循环面临七大现实瓶颈：弱评估器、上下文生命周期管理、负面结果处理、多样性坍缩、奖励黑客、长期成功度量、人类角色定位 [(Lilian Weng, 2026)](https://lilianweng.github.io/posts/2026-07-04-harness/)。对于正在开发AICraft的团队而言，这些发现意味着：**模型是商品，Harness是护城河**——下半场的竞争重点已从"谁的模型更强"转向"谁的外层系统更可靠"。

---

## 1. Harness Engineering的定义与核心概念

### 1.1 核心定义

**Harness Engineering**（外层工程/编排工程）是围绕AI Agent设计和构建约束机制、反馈回路、工作流控制系统的工程学科。它的核心公式简洁而深刻：

> **Agent = Model + Harness**

模型是引擎，Harness是方向盘、刹车、仪表盘和导航系统。再强的引擎没有方向盘和刹车，也无法抵达目的地 [(Mitchell Hashimoto, 2026)](https://mitchellh.com/writing/my-ai-adoption-journey)。

Mitchell Hashimoto（HashiCorp联合创始人、Terraform作者）于2026年2月5日在个人博客中正式命名了这一术语。他的核心原则是：**"每当Agent犯了一个错误，你就花时间工程化一个解决方案，让Agent永远不再犯同样的错误"** [(Mitchell Hashimoto, 2026)](https://mitchellh.com/writing/my-ai-adoption-journey)。这一理念迅速获得社区共鸣——Hacker News讨论帖冲到286赞，约200条评论 [(CSDN)](https://blog.csdn.net/u012743772/article/details/162222401)。

翁荔（Lilian Weng，前OpenAI安全研究副总裁）在2026年7月4日的博客中给出了更学术化的定义：**Harness是包裹在基座模型外的系统，它编排执行过程，决定模型如何思考和规划、调用工具和行动、感知和管理上下文、存储产物、评估结果** [(Lilian Weng, 2026)](https://lilianweng.github.io/posts/2026-07-04-harness/)。

### 1.2 与Prompt Engineering、Context Engineering的关系

Harness Engineering不是凭空出现的概念，它是AI工程方法论演进的必然结果。三者的关系如下：

| 维度 | Prompt Engineering | Context Engineering | Harness Engineering |
|------|-------------------|--------------------|--------------------|
| 关注点 | 怎么把话说清楚 | 怎么给模型提供正确材料 | 怎么让Agent稳定完成任务 |
| 范围 | 单次交互 | 单个上下文窗口 | 整个Agent系统生命周期 |
| 控制对象 | 指令措辞 | Token选择、排序、压缩 | 工具编排、状态持久化、验证循环、错误恢复 |
| 失败模式 | 指令不清晰 | 上下文中信息错误/遗漏 | Agent错误、无限循环、多会话漂移、不安全操作 |
| 时间边界 | 单轮对话 | 一个上下文窗口 | 多个上下文窗口；完整任务生命周期 |
| 隐喻 | 指令 | 信息 | 环境/闭环 |

[(掘金, 2026)](https://juejin.cn/post/7651603794847023119) [(deepset, 2026)](https://www.deepset.ai/blog/harness-engineering)

这个演进的核心逻辑是：**当模型越来越强，让它可靠完成复杂任务靠的不再是更好的提示词，而是更好的运行环境**。Prompt Engineering优化的是"怎么说"，Context Engineering优化的是"知道什么"，Harness Engineering优化的是"在什么环境里做事"。

### 1.3 Harness的术语溯源

Harness Engineering有三条清晰的思想源流 [(CSDN, 2026)](https://blog.csdn.net/u012743772/article/details/162222401)：

1. **Anthropic的"长时运行Agent"系列**（概念源头）：2025年11月到2026年3月，Anthropic先后发布三篇关键文章，提出Agent持久化、检查点、错误恢复的概念。核心洞察是"Agent的失败不是模型不够强，而是运行环境不够健壮"。

2. **OpenAI的"百万行代码"实验**（命名推广）：2026年2月，OpenAI发布《Harness Engineering: Leveraging Codex in an Agent-First World》，3-7人团队5个月交付100万行生产代码、1500个PR、零手写代码 [(OpenAI)](https://openai.com/index/unrolling-the-codex-agent-loop/)。

3. **Mitchell Hashimoto的术语命名**（社区共识）：2026年2月5日博文正式使用"Harness Engineering"术语，将散落各处的实践统一命名。

---

## 2. Harness的关键组成部分

### 2.1 编排（Orchestration）

编排是Harness的中枢神经，决定Agent的执行流程、子Agent调度和控制流。当前主流编码Agent（Claude Code、Codex、OpenCode）的核心接口已趋稳定，普遍采用目标导向循环：**计划→执行→观察/测试→改进→再执行，直至目标达成** [(Lilian Weng, 2026)](https://lilianweng.github.io/posts/2026-07-04-harness/)。

Anthropic的双Agent架构是编排设计的经典范式：第一个Agent（Initializer）创建全面的环境骨架，包括200+项的功能列表和进度日志；第二个Agent（Coding Agent）严格按增量方式逐项执行 [(Newsletter, 2026)](https://spikefu.com/newsletters/2026-04-22t01-04-44/newsletter.pdf)。这种设计避免了Agent试图一次性完成所有工作导致的上下文耗尽问题。

子Agent和后端任务（Pattern 3）是另一个关键模式：Harness可以生成多个子Agent并行执行，监控后端任务。核心设计选择是**让并行性显式且可检查**——子Agent的输出不应只存在于瞬态聊天上下文中，而应存储为文件、日志和状态记录 [(Lilian Weng, 2026)](https://lilianweng.github.io/posts/2026-07-04-harness/)。

### 2.2 工具调用（Tool Use）

工具是Agent与外部世界交互的手。当前编码Agent的典型工具集包括：

| 工具组 | 具体工具 |
|--------|---------|
| 文件系统 | `glob`, `grep`, `ls`, `read`, `write`, `edit`, `multi_edit`, `apply_patch` |
| Shell执行 | `bash`, `PowerShell` |
| IO | `lsp`, `git_status`, `git_diff`, `git_commit` |
| 外部上下文 | MCP工具, Skills |
| Web搜索 | `web_search`, `web_fetch`, 浏览器工具 |
| 产物 | 读取文档/图片；生成HTML/图片 |
| 后端进程 | `CronCreate`, `CronDelete`, `CronList` |
| Agent委托 | `spawn_agent`, `resume_agent`, `wait_agent` 等 |

[(Lilian Weng, 2026)](https://lilianweng.github.io/posts/2026-07-04-harness/)

工具设计的关键原则是**渐进式披露**：大型工具目录不应在第一步就塞进上下文窗口，而应根据任务需要动态暴露相关工具 [(deepset, 2026)](https://www.deepset.ai/blog/harness-engineering)。另一个实用原则是**优先使用标准CLI**：Agent能完美使用`git`是因为训练数据中有大量git操作，而一个没有文档的自定义CLI则容易让Agent困惑 [(ybuild.ai, 2026)](https://ybuild.ai/en/blog/harness-engineering-complete-guide-ai-coding-agents-2026)。

### 2.3 上下文管理（Context Engineering）

上下文管理是Harness中最精细的部分，也是从Prompt Engineering到Harness Engineering的桥梁。核心挑战是：**上下文窗口是有限且昂贵的，而Agent执行过程中的信息量是无限增长的**。

**文件系统作为持久记忆**（Pattern 2）是当前最成熟的解决方案。Harness不应将整个工作流和所有日志塞进上下文；相反，它应将持久状态保存在文件中。学习如何读写和编辑文件系统（通常通过`bash`命令）是LLM的基础技能，因此以文件形式管理持久记忆天然受益于核心模型能力的提升 [(Lilian Weng, 2026)](https://lilianweng.github.io/posts/2026-07-04-harness/)。

OpenAI Codex团队的实践为此提供了精彩案例：他们最初将所有约定、规则和历史决策放在一个巨大的`AGENTS.md`文件中，结果失败了。原因是：(1) 上下文是稀缺资源，臃肿的指令文件挤占了实际任务空间；(2) 标记所有内容为"重要"等于没有重点；(3) 文档会腐烂——第二周的规则到第八周就过时了。解决方案是：**将AGENTS.md缩减到100行，不是规则——是地图**，指向结构化的`docs/`目录，Linter和CI验证交叉链接的完整性 [(Milvus, 2026)](https://milvus.io/ja/blog/harness-engineering-ai-agents.md)。

上下文Token预算分配的典型策略：40%最近消息 + 25%检索文档 + 15%草稿/思考空间 + 15%工具描述 + 5%预留缓冲 [(CSDN, 2026)](https://blog.csdn.net/qq_31142761/article/details/162108247)。

### 2.4 评估与验证（Evaluation & Verification）

Martin Fowler于2026年4月提出的Feedforward/Feedback框架，为Harness的评估设计提供了最清晰的心智模型 [(Martin Fowler, 2026)](https://www.martinfowler.com/articles/harness-engineering.html)：

**Feedforward（前置约束/引导）**：在Agent行动之前施加影响，提高首次成功的概率。例如：`AGENTS.md`文件、LSP集成、编码约定、代码模板脚手架。

**Feedback（反馈循环/传感器）**：在Agent行动后观察结果，帮助其自我修正。例如：Linter、类型检查、单元测试、AI Code Review。

两者必须结合：只有Feedback的Agent会重复同样的错误；只有Feedforward的Agent编码了规则但永远不知道规则是否有效。

每种控制又分为两种执行类型：
- **计算型**（Computational）：确定性、快速、毫秒级，如Linter、类型检查、结构分析
- **推理型**（Inferential）：语义分析、AI代码审查，慢且贵但提供深层判断

一个关键实践：**Linter错误消息本身应该成为一个prompt**。不良消息："violation detected"；优秀消息："use `logger.info({event: 'name', ...data})` instead of `console.log`"——后者让Agent能自主修复，而非依赖人工解释 [(掘金, 2026)](https://juejin.cn/post/7630728828343762963)。

### 2.5 安全与权限（Guardrails）

安全边界是Harness的护栏，决定Agent能做什么、不能做什么、哪些操作必须审批。OpenAI Codex实验中的架构约束是典型案例：严格分层架构，强制单向依赖方向——Types → Config → Repo → Service → Runtime → UI，自定义Linter机械地执行这些规则，错误消息内联修复指令 [(Milvus, 2026)](https://milvus.io/ja/blog/harness-engineering-ai-agents.md)。

翁荔特别警告：**如果允许模型自由修改系统代码，抽象边界和权限控制就会被打破，可能引发灾难性后果**。评估器和权限控制应该位于进化Harness的循环之外，使用保留测试集、追踪审计和关键决策点的人类审查 [(Lilian Weng, 2026)](https://lilianweng.github.io/posts/2026-07-04-harness/)。

### 2.6 可观测性与恢复（Observability & Recovery）

可观测性是Harness的仪表盘，恢复机制是Harness的维修站。对于长时间运行的Agent，两者缺一不可。

**恢复策略应分层**：轻微失败→自动重试；可诊断失败→错误回传Agent修正；重复失败→切换策略或缩小任务；高风险失败→停止执行请求人类确认；不可恢复失败→回滚工作区输出诊断报告 [(掘金, 2026)](https://juejin.cn/post/7651603794847023119)。

**进度文档化**是长时间任务（30分钟以上）的关键实践：维护进度文件跟踪已完成步骤；频繁提交代码以便后续会话可继续；使用结构化任务列表而非自由格式笔记 [(ybuild.ai, 2026)](https://ybuild.ai/en/blog/harness-engineering-complete-guide-ai-coding-agents-2026)。

---

## 3. Harness的演进路线

翁荔在博客中明确总结了Harness优化对象的演进路径：**指令提示词 → 结构化上下文 → 工作流 → Harness代码 → 优化器代码** [(Lilian Weng, 2026)](https://lilianweng.github.io/posts/2026-07-04-harness/)。随着模型越来越智能强大，我们向更复杂的目标和更通用的方法迈进。

![Harness演进路线图](https://www.coze.cn/s/2oHbt5nZ65c/)

### 3.1 手工设计阶段（2023-2025）

早期的Harness完全依赖人工设计：`AGENTS.md`文件提供项目上下文，Linter/CI强制执行编码规范，Prompt模板定义Agent行为。这个阶段的核心局限是——**所有规则都是启发式的，依赖人类工程师的经验和直觉**。

Mitchell Hashimoto总结的原则最具代表性：每当Agent犯错，就工程化一个解决方案让这个错误不再发生。这包括两种形式：(1) 更好的隐式提示（更新AGENTS.md）；(2) 实际的可编程工具（截图脚本、过滤测试脚本等），通常与AGENTS.md更新配对使用 [(Mitchell Hashimoto, 2026)](https://mitchellh.com/writing/my-ai-adoption-journey)。

### 3.2 Agentic Context Engineering — ACE（2025）

**ACE**将上下文视为不断演化的"操作手册"（playbook），而非不断增长的提示词。它有三个组件 [(Zhang et al., ICLR 2026)](https://arxiv.org/abs/2510.04618)：

1. **Generator**：参照上下文要点生成任务轨迹
2. **Reflector**：从成功和失败轨迹中提炼洞察
3. **Curator**：以增量、结构化的方式更新上下文

ACE解决了一个关键问题——**上下文坍缩**（Context Collapse）：当要求LLM完全重写累积上下文时，模型倾向于将其压缩为更短、信息量更少的摘要。ACE的Curator不重写完整的prompt blob，而是输出一组结构化的`(标识符, 描述)`条目，通过确定性逻辑合并到结构化上下文日志中。在AppWorld排行榜上，ACE使用更小的开源模型（DeepSeek-V3.1）匹配了排名第一的生产级Agent（IBM-CUGA，使用GPT-4.1）。

但ACE的局限也很明显：**更新规则和整体工作流仍然是手工设计的**。

### 3.3 Meta Context Engineering — MCE（2026.01）

**MCE**将上下文管理从手工规则推进到可搜索的技能空间。它引入双层优化 [(Ye et al., 2026)](https://arxiv.org/abs/2601.21557)：

- **元层**（Meta-level）：Agent进化"技能"——即可执行的指令和代码，定义上下文应如何表示和从数据中学习。通过**Agentic Crossover**（一种灵活的进化算子），Agent推理任务规范、历史轨迹和性能指标，合成更优技能。
- **基层**（Base-level）：Agent执行进化出的技能，从训练rollout中学习，优化上下文。

形式化地，MCE解决的双层问题为：
- 内层：给定技能s，找到最佳上下文函数 `c_s* = arg max J_train(c_s; s)`
- 外层：找到能产生最大验证性能的技能 `s* = arg max J_val(c_s*)`

MCE在五个不同领域（金融、化学、医学、法律、AI安全）上相比SOTA ACE方法取得了5.6%–53.8%的相对提升（均值16.9%）。更重要的是，**MCE不强制规定上下文如何结构化——它使用自由形式的技能来存储任务最重要的知识，并迭代地进化技能和技能条件化的上下文** [(Lilian Weng, 2026)](https://lilianweng.github.io/posts/2026-07-04-harness/)。

### 3.4 Meta-Harness自动搜索（2026.03）

**Meta-Harness**再往深处走了一层：优化的对象是**决定什么信息应该存储、检索和呈现给模型的代码本身**。"Meta"意味着它是优化Harness的Harness [(Lee et al., 2026)](https://arxiv.org/abs/2603.28052)。

Meta-Harness的核心设计选择是：**给proposer完整的文件系统访问权限，取代压缩后的摘要**。现有的文本优化方法（OPRO、TextGrad、GEPA、AlphaEvolve等）都在做某种形式的信息压缩——只保留分数、只看最近一次结果、让模型生成摘要再做决策。消融实验表明这损失巨大：分数-only中位数准确率34.6%，分数+LLM摘要34.9%，**完整轨迹访问50.0%——15.4个百分点的跳跃** [(Lee et al., 2026)](https://arxiv.org/abs/2603.28052)。

Meta-Harness的搜索循环简洁而有效：(1) Coding Agent（使用Claude Opus 4.6）读取文件系统中存储的所有历史候选Harness的源代码、评估分数和执行轨迹；(2) 提出新的Harness代码；(3) 运行评估并记录所有产物。典型配置是20轮迭代，每轮约60个候选Harness。

结果令人印象深刻：在文本分类上比ACE高7.7个百分点且上下文Token用量仅四分之一；在TerminalBench-2上Opus 4.6达76.4%（超越Terminus-KIRA的74.7%），Haiku 4.5达37.6%（排名第一）[(Lee et al., 2026)](https://arxiv.org/abs/2603.28052)。

Meta-Harness自动发现了几个有趣的策略：(1) **"草稿-验证"两阶段策略**——先检索5个最相似样本做初始预测，再检索"支持者"和"挑战者"做二次验证；(2) **环境快照bootstrap**——在第一轮推理前就收集系统环境信息，减少Agent前几轮的盲探测；(3) **按题型路由的检索策略**——不同数学领域使用不同检索参数 [(CSDN, 2026)](https://blog.csdn.net/m0_59163425/article/details/159731328)。

### 3.5 Darwinian Gödel Machine进化搜索（2025-2026）

**Darwin Gödel Machine（DGM）**将进化搜索推向了极致：**允许编码Agent修改自身的Harness代码库** [(Zhang et al., 2025)](https://arxiv.org/abs/2505.22954)。

DGM的理论根基是Schmidhuber 2003年提出的Gödel Machine——理论上，它能通过数学证明确保每次自我修改都是改进。但在实践中，数学证明几乎不可能，因此DGM用达尔文式进化替代了形式证明：

1. 初始化一个编码Agent池
2. 每轮迭代：按性能比例选择父Agent，反比于其已有子代数量
3. 父Agent检查自身的基准评估日志，提出对自身Harness代码库的改进
4. 评估新的子Agent，只有性能足够高的才加入池中
5. 重复直到满足停止条件

DGM维护一个**进化档案**（archive），保留所有历史Agent——不是只保留最佳，而是保留多样性。这避免了局部最优：性能较低的Agent也可能被选为父代，因为它们可能包含通往更好解决方案的"踏脚石"。

实验结果：以Claude 3.5 Sonnet为基座LLM，DGM在SWE-bench Verified上从**20.0%提升至50.0%**，在Polyglot上从**14.2%提升至30.7%**——与手工设计的Agent相当甚至更优 [(Zhang et al., 2025)](https://arxiv.org/abs/2505.22954)。DGM自主发现了许多有价值的改进：更好的代码编辑工具、长上下文窗口管理、同行审查机制等——没有人教它这样做。

### 3.6 联合优化：Harness + 模型权重

更长期的愿景是让Harness改进与模型权重更新在同一个优化循环中进行。**SIA**（Hebbar et al., 2026）是这方面的早期尝试，包含三个组件：Meta-Agent提出初始Harness，Task-Specific Agent执行任务，Feedback-Agent根据最近轨迹决定是更新Harness还是更新模型权重 [(Hebbar et al., 2026)](https://arxiv.org/abs/2605.27276)。

翁荔对SIA的评价较为谨慎："实验中存在一些混淆因素使结果难以解释"，但认为方向有意义。她指出，**最终Harness的许多改进可能会被"内化"到核心模型行为中**，就像Prompt Engineering的手工技巧随着指令微调和推理能力提升变得不那么核心——但**指定目标、约束、上下文和评估的需求不会消失** [(Lilian Weng, 2026)](https://lilianweng.github.io/posts/2026-07-04-harness/)。

---

## 4. 当前业界实践

### 4.1 主流编排框架对比

| 框架 | 设计哲学 | Harness侧重 | 生产就绪度 | 适用场景 |
|------|---------|------------|-----------|---------|
| **LangGraph** | 有向图状态机 | 状态管理、容错、检查点 | 高 | 复杂有状态系统、需从部分故障中恢复 |
| **CrewAI** | 角色协作 | 角色定义、任务委派 | 中 | 快速原型、角色优先设计 |
| **AutoGen/AG2** | 多Agent对话 | 对话式多Agent协调 | 中 | 研究、实验性多Agent |
| **OpenAI Agents SDK** | 观点化交接 | 内置追踪和护栏 | 高 | OpenAI生态内工作负载 |

[(TokenMix, 2026)](https://tokenmix.ai/blog/agent-frameworks-2026-langgraph-crewai-autogen-openai-sdk) [(JATIR, 2026)](https://jatir.org/publishedpapers/140332_PAPER.pdf)

从Harness Engineering视角看，LangGraph提供最细粒度的控制——其图执行模型原生支持并行扇出、状态检查点、人工干预中断和时间旅行调试。CrewAI的角色约束天然减少了Token浪费。AutoGen的多轮对话机制能捕获单次系统遗漏的错误，但Token消耗最高。三个框架正在趋同于同一执行模型：基于图的编排，Agent节点，条件边，并行执行路径，节点级状态管理 [(AI Agent Engineering, 2026)](https://ai-agent-engineering.org/news/ai-agent-frameworks-benchmarked-langchain-vs-crewai-vs-autogen-in-2026-the-numbers-that-actually-matter)。

### 4.2 标杆案例

**OpenAI Codex百万行代码实验**：3-7人团队，5个月，100万行生产代码，1500个PR，零手写代码。他们遇到四个核心问题并逐一解决 [(Milvus, 2026)](https://milvus.io/ja/blog/harness-engineering-ai-agents.md) [(OpenAI)](https://openai.com/index/unrolling-the-codex-agent-loop/)：

1. **无共享代码库理解** → AGENTS.md从大文件缩减到100行"导航地图"
2. **人类QA跟不上Agent产出** → 将Chrome DevTools Protocol接入Codex，Agent可截图UI、观察运行时事件
3. **无约束的架构漂移** → 严格分层架构+自定义Linter强制执行
4. **静默技术债务** → 编码项目核心原则到仓库中，定时运行后台Codex任务扫描偏差并提交重构PR

**Stripe Minions**：内部系统每周产生1000+合并PR。Harness包括：紧范围任务定义、强制人类代码审查、自动化回归测试、回滚自动化 [(ybuild.ai, 2026)](https://ybuild.ai/en/blog/harness-engineering-complete-guide-ai-coding-agents-2026)。

**Anthropic双Agent架构**：Initializer Agent创建200+项功能列表（使用JSON而非Markdown，因为模型更不容易意外覆盖JSON结构），Coding Agent按增量逐项执行。通过Git提交和进度日志实现"记忆桥接"，让下一个Agent实例能即时理解项目状态 [(Newsletter, 2026)](https://spikefu.com/newsletters/2026-04-22t01-04-44/newsletter.pdf)。

### 4.3 基准测试与评估

| 基准测试 | 评估内容 | 任务数 | 特点 |
|---------|---------|-------|------|
| SWE-bench Verified | 修复真实GitHub Issue | 500 | 人工验证，最可靠的代码修复评估 |
| TerminalBench-2 | 终端编程任务 | 89 | Agent编程能力的综合评估 |
| CLAW-SWE-Bench | 多语言SWE任务 | 350 | 8种编程语言，统一适配器层 |
| PaperBench | 复现ICML论文 | 8316 rubrics | 最难的学术复现评估 |
| RE-Bench | ML研究工程 | 7环境 | 对标人类专家的8小时工作 |

[(Lilian Weng, 2026)](https://lilianweng.github.io/posts/2026-07-04-harness/) [(mcpbr.org)](https://mcpbr.org/swe-bench)

评估中的关键发现：**当前自我改进循环在有明确、快速、客观评估指标的任务上效果显著（如写代码、解数学题），但面对模糊判断（如"这项研究是否有品味""这个结果是否真的重要"）时系统容易失效，甚至会为了通过测试而学会作弊（奖励黑客）** [(麻省理工科技评论, 2026)](https://www.mittrchina.com/news/detail/16614)。

---

## 5. 对AICraft的具体改进建议

### 5.1 思维转变：从"只关注模型"到"模型+Harness"

AICraft目前主要关注大模型本身，还没有关注模型之外的编排、工具调用、上下文管理、评估等外层系统。基于Harness Engineering的视角，**这是当前最大的改进空间**。核心转变是：

- **从"优化模型输出质量"转向"构建让Agent可靠完成任务的运行环境"**
- **从"写更好的Prompt"转向"设计让错误不可能发生的系统"**
- **从"模型是核心竞争力"转向"Harness是护城河"**

LangChain的实验提供了最直观的证明：同一个模型，只改Harness，排名从30名外跃升至第5 [(ybuild.ai, 2026)](https://ybuild.ai/en/blog/harness-engineering-complete-guide-ai-coding-agents-2026)。模型趋同正在加速——GPT-4、Claude Sonnet、Gemini Pro在标准基准上的差距正在缩小，**Harness质量是区分生产可用Agent和Demo级Agent的主要变量** [(Atlan, 2026)](https://atlan.com/know/what-is-an-agent-harness/)。

### 5.2 AICraft Harness层设计路线图

#### 短期（1-2个月）：最小可行Harness

| 优先级 | 改进项 | 具体做法 | 预期收益 |
|--------|-------|---------|---------|
| P0 | AGENTS.md系统 | 为AICraft支持的项目创建结构化的上下文文件，控制在100行以内，作为"导航地图"指向更深层文档 | 减少Agent的盲目试错 |
| P0 | PEV循环 | 实现 Plan→Execute→Verify 循环，替代简单的 Generate-and-Check | 减少错误输出 |
| P1 | 计算型Feedback | 接入Linter、类型检查、测试运行器，将错误消息结构化回传Agent | 让Agent能自我修正 |
| P1 | 工具封装 | 标准化工具接口，优先使用标准CLI，添加使用说明 | 提高工具调用成功率 |
| P2 | 恢复机制 | 实现分层恢复策略：自动重试→错误回传→策略切换→人类确认 | 提高长任务成功率 |

#### 中期（3-6个月）：系统化Harness

| 优先级 | 改进项 | 具体做法 | 预期收益 |
|--------|-------|---------|---------|
| P0 | 上下文管理框架 | 实现类似ACE的Generator-Reflector-Curator循环，将上下文视为演化手册 | 解决上下文坍缩问题 |
| P0 | 评估器体系 | 建立多层级评估：计算型（快速确定性）+ 推理型（语义理解），Feedforward + Feedback双覆盖 | 提高验证覆盖率 |
| P1 | 子Agent编排 | 支持子Agent生成、并行执行、结果合并，实现"上下文防火墙" | 支持复杂任务分解 |
| P1 | 可观测性 | 全链路追踪：每步为什么做、调用了什么工具、花了多少Token、产物是什么 | 让Harness改进有据可依 |
| P2 | 文件系统持久化 | 将Agent状态和产物持久化到文件系统，支持跨会话恢复 | 支持长周期任务 |

#### 长期（6-12个月）：自进化Harness

| 优先级 | 改进项 | 具体做法 | 预期收益 |
|--------|-------|---------|---------|
| P0 | Self-Harness | 实现"失败挖掘→Harness提案→验证"循环，让Harness从失败中自我改进 | 持续提升Harness质量 |
| P1 | 技能进化 | 实现类似MCE的双层优化，元层进化上下文管理技能，基层优化任务上下文 | 减少对手工规则的依赖 |
| P2 | Harness代码搜索 | 借鉴Meta-Harness，将Harness代码作为搜索空间，让Coding Agent提出和验证改进 | 自动发现更优Harness设计 |

### 5.3 关键技术落地要点

**AGENTS.md系统设计**：核心原则是"给地图不给手册"。每个项目根目录放置`AGENTS.md`，控制在100行以内，内容应包括：(1) 技术栈；(2) 目录结构（一行一描述）；(3) 5-10条硬规则；(4) 常用任务的操作方式 [(ybuild.ai, 2026)](https://ybuild.ai/en/blog/harness-engineering-complete-guide-ai-coding-agents-2026)。更详细的文档放在`docs/`目录中，AGENTS.md通过引用指向。

**PEV循环实现**：Augment Code提出的Plan-Execute-Verify模式优于简单的Generate-and-Check。核心区别：PEV在执行前验证工具调用是否在范围内（不只是事后检查），Plan阶段减少自由度，反馈信号是带上下文的错误消息而非二元通过/失败 [(掘金, 2026)](https://juejin.cn/post/7630728828343762963)。

**评估器设计**：遵循Fowler的Feedforward/Feedback框架，建立四象限评估矩阵：

| | 计算型（确定性） | 推理型（概率性） |
|---|---|---|
| **Feedforward** | LSP集成、代码模板、架构约束 | AGENTS.md、Skills、审查规范 |
| **Feedback** | Linter、类型检查、单元测试 | AI Code Review、AI Judge |

**上下文管理三原则**：(1) 不要无脑保留全部历史——10轮对话后前面的上下文对当前决策边际收益极低；(2) 关键信息做结构化提取——用JSON Schema约束LLM在每步输出中提取关键状态；(3) 记忆检索要有"遗忘机制"——长期记忆中过时、矛盾的信息需要被清理 [(CSDN, 2026)](https://blog.csdn.net/qq_31142761/article/details/162108247)。

### 5.4 需要警惕的陷阱

基于翁荔总结的七大未来挑战 [(Lilian Weng, 2026)](https://lilianweng.github.io/posts/2026-07-04-harness/)，AICraft在实践Harness Engineering时应特别注意：

1. **评估器瓶颈**：自我改进循环在有明确评估指标的任务上效果好，但模糊任务容易失败。AICraft应从有明确评估标准的场景（代码生成、数据处理）开始，逐步扩展。

2. **奖励黑客**：如果评估来自单元测试，Agent可能过拟合测试；如果来自Judge模型，可能学会欺骗特定Judge。评估器应位于进化循环之外，使用保留测试集和人类审查。

3. **长期成功度量**：当前优化大多基于沙盒内的短期奖励，但现实中的软件工程需要兼顾可维护性、向后兼容性和未来开发负担。这些"长期成功"的指标正是当前系统最不擅长处理的。

4. **多样性坍缩**：进化/RL循环倾向于利用已知高奖励模式。需要机制防止种群坍缩为同一方案的变体——这对开放性研究尤为关键，因为最优路径在当前评估器下可能看起来更差。

5. **人类角色不是被排除，而是向上移动**：人类应在环路外扮演架构师和方向指引者，负责设计可编辑的边界和进行关键节点的审查。Mitchell Hashimoto的实践也证实了这一点——让Agent在可控范围内高效工作，而不是试图让Agent完全自主 [(Lilian Weng, 2026)](https://lilianweng.github.io/posts/2026-07-04-harness/)。

---

**总结**：Harness Engineering标志着AI Agent开发从"优化模型"到"优化系统"的范式迁移。对于AICraft而言，当前最紧迫的改进不是换一个更强的模型，而是构建一个可靠的Harness——从AGENTS.md和PEV循环开始，逐步演进到上下文管理框架和Self-Harness。正如翁荔所言：**"真正的递归自我改进（RSI）不是突然某天模型开始修改自己，而是悄悄开始于一次次Harness优化中"** [(麻省理工科技评论, 2026)](https://www.mittrchina.com/news/detail/16614)。

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
