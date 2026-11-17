# 雾计算工作流调度论文：Java 代码阅读与 Python 复现方案

- **编写日期：2026-10-08（America/Los_Angeles；对应 UTC 日期为 2026-10-09）**
- **适用论文：** Xu 等，2023，*Genetic Programming for Dynamic Workflow Scheduling in Fog Computing*。
- **对应代码包：** `Fog-Computing-multiDeviceDebug.zip`。
- **读者基础：** 学过 Python 和 C/C++，对 Java 较陌生。
- **主要目的：** 理解论文相关 Java 实现，并用 Python 实现相同的模拟、调度、规则求值、GP 演化和实验评估功能。
- **可选扩展：** 在经过验证的 Python 基线上探索新规则、新特征或新演化方法。
- **依据与范围：** 本方案基于上传论文及源码的静态检查；尚未完成源码运行验证、完整正确性审计或 Python 复现。

## 1. 总体建议与学习顺序

不必先系统学完 Java。先补齐阅读所需的 Java 基础，再围绕项目学习，并逐步建立 Python 对照实现。

推荐顺序：

1. **补 Java 阅读基础和调试能力。**
2. **快速看项目入口和配置，建立整体结构。**
3. **理解任务、资源、执行选项和全局状态。**
4. **读懂固定规则下的离散事件模拟器。**
5. **实现小规模、固定输入的 Python 模拟器，并与 Java 对照。**
6. **补齐 DAX 解析、随机实例、多设备和统计。**
7. **理解特征与 GP 表达式求值，在 Python 中执行固定 GP 规则。**
8. **理解适应度评估，再实现 GP 演化。**
9. **核对论文实验配置，开展正式实验。**
10. **基线验证完成后，再考虑扩展研究。**

核心标准是：能说明输入、状态变化和输出，并用 Python 重现行为。不是把每句 Java 翻译成中文，也不是先读完所有框架代码。

## 2. “相同功能”应如何定义

建议区分三层目标：

| 层次 | 目标 | 验证方式 |
| --- | --- | --- |
| 第一层：确定性行为一致 | 相同固定实例和规则下，得到相同任务分配、执行过程和指标 | 对照决策与事件轨迹 |
| 第二层：算法与实验机制一致 | 实例分布、特征定义、演化算子、重置与训练评估机制一致 | 小规模算子验证、配置核对、重复实验 |
| 第三层：论文结果复现 | 在论文场景中复现主要性能与统计趋势 | 正式实验与统计比较 |

不同语言使用不同随机生成器时，即使 seed 相同，也不保证每次演化产生完全相同的树和曲线。应先实现第一层，再推进第二、第三层。

对论文描述与代码行为不一致之处，分别记录“源码行为”和“论文设定”。先建立明确的对照基线，之后再单独修改，避免把移植错误和主动改变模型混在一起。

## 3. Java 学习范围与停止标准

### 3.1 推荐学习顺序

| 顺序 | 内容 | 在本项目中的用途 | 掌握标准 |
| --- | --- | --- | --- |
| 1 | 基本类型、控制流、数组、方法、整数和浮点运算 | 阅读公式与循环 | 能判断运算结果及类型 |
| 2 | 类、对象、字段、构造函数及重载，`this`、`static`、`final` | 理解模型初始化 | 能写并使用一个 Task 类 |
| 3 | 对象引用、可变对象、浅复制与深复制 | 理解共享状态和 GP 子代 | 能判断一次修改会影响哪些对象 |
| 4 | 抽象类、接口、继承、重写、多态，`super`、`instanceof` | 理解事件与规则 | 能通过父类引用调用子类方法 |
| 5 | 泛型、List、ArrayList、LinkedList、Map、PriorityQueue | 理解队列、集合和依赖 | 能解释数据结构及排序依据 |
| 6 | `compareTo()`、`equals()`、`hashCode()`、enum | 理解事件排序与类型 | 能说明比较和平分处理 |
| 7 | 包、导入、异常、文件读取、JDK、classpath | 编译运行 | 能从源码运行小程序 |
| 8 | 断点、单步、条件断点、Watch、调用栈 | 跟踪模拟过程 | 能跟踪一个任务的完整生命周期 |

可先安排约 **8～15 小时**，这是有 Python/C/C++ 基础时的参考投入，不是保证完成的时间。

### 3.2 两个必须理解的语义

- Java 按值传递参数。对象参数传递的是引用的值，修改该对象内部状态，会影响其他地方引用的同一对象。
- `final` 修饰对象引用，不表示对象内部不可修改。例如列表引用不能重新赋值，列表仍可增加或删除元素。

### 3.3 可以暂时跳过

Spring、Web 开发、数据库、GUI、JVM 调优、深入并发编程和完整的 Java 工程体系。反射先理解“框架可根据配置中的类名创建对象”即可。

### 3.4 进入源码阅读的最低标准

能够自行写出一个任务类、一个抽象事件类和两个事件子类，用优先队列按时间触发，并用调试器观察对象状态。

不必等到 Java 熟练后才开始 Python 实现。

## 4. 项目结构和目录使用说明

### 4.1 路径约定

压缩包解压后的项目根目录名为：

`Fog-Computing-multiDeviceDebug/`

本文的代码路径均**从解压目录开始写到具体文件**，不是电脑盘符下的绝对路径。例如：

`Fog-Computing-multiDeviceDebug/src/mengxu/simulation/DynamicSimulation.java`

若你已在 IDE 中打开项目根目录，则去掉最前面的 `Fog-Computing-multiDeviceDebug/` 即可定位。文中所列代码路径已按本次上传包实际文件核对；大小写和拼写应原样保留。

### 4.2 主要目录

| 项目内目录 | 用途 | 阅读优先级 |
| --- | --- | --- |
| `Fog-Computing-multiDeviceDebug/src/mengxu/taskscheduling/` | 工作流、任务、资源和实例模型 | 高 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/simulation/` | 离散事件模拟与系统状态 | 高 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/rule/` | 调度规则接口与 GP 规则 | 高 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/algorithm/` | 基准算法及单树、多树 GP 配置和实现 | 按阶段读 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/gp/` | 规则树、特征、函数节点与演化支持 | 模拟器之后 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/ruleevaluation/` | 规则评估模型 | GP 演化之前 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/ruleoptimisation/` | GP 个体与评估模型的连接 | GP 演化之前 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/ruleanalysis/` | 结果读取、测试与分析 | 后期 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/util/` | 随机采样、表达式解析 | 按调用需要读 |
| `Fog-Computing-multiDeviceDebug/src/ec/` | ECJ 演化计算框架 | 后期按需读 |
| `Fog-Computing-multiDeviceDebug/dax/` | 运行时使用的工作流 XML 数据 | 实例生成阶段 |
| `Fog-Computing-multiDeviceDebug/libraries/` | Java 外部依赖 | 配置环境时查看 |
| `Fog-Computing-multiDeviceDebug/out/` | 已编译输出 | 不作为源码阅读起点 |

名称提醒：`Job` 对应工作流；`TaskOption` 是任务在某个处理器上执行的候选方案；`Process` 是一次任务执行记录，不是操作系统进程。

## 5. 代码阅读顺序：文件、目录、重点和完成标准

下面的编号是建议执行顺序。每轮只读当前目标所需的方法，允许回看；不要求一次读完整个文件。

### 第 1 步：快速看入口和配置

| 文件所在路径 | 阅读重点 |
| --- | --- |
| `Fog-Computing-multiDeviceDebug/README.md` | 项目结构、依赖、运行入口 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/gp/GPMain.java` | `main()`：配置路径、命令行覆盖项、实验 seed 和输出 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/gp/GPRun.java` | 参数加载、初始化、`state.run()` 的连接关系，先略读 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/algorithm/multipletreegp/multipletreegp-dynamicBaseline.params` | state、problem、eval-model、两棵树、种群、算子和场景参数 |

**完成标准：** 能指出“从哪个入口启动、哪个配置创建哪种对象、实验规模在哪里设定”。

此阶段不要沿入口逐行深入整个 ECJ。当前多树配置种群大小为 100，论文表 VI 为 1000，应区分调试配置与正式复现配置。

### 第 2 步：看一次固定规则模拟怎样启动

| 文件所在路径 | 阅读重点 |
| --- | --- |
| `Fog-Computing-multiDeviceDebug/src/mengxu/SECtest.java` | `main()`、`HEFTcheck()`：规则创建、模拟器构造、`run()`、指标读取 |

**完成标准：** 能写出“创建规则 → 创建模拟器 → 运行 → 读取指标”的最小流程。

注意：`HEFTcheck()` 当前实际加载的是 GP 表达式规则，不可仅凭方法名认定它在运行 HEFT。随后建议在自己的调试入口中使用简单固定规则。

### 第 3 步：理解工作流、任务和资源模型

| 文件所在路径 | 阅读重点 |
| --- | --- |
| `Fog-Computing-multiDeviceDebug/src/mengxu/taskscheduling/Job.java` | 工作流发布时间、任务列表、完成判定、完成记录 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/taskscheduling/Task.java` | 父子依赖、`complete`、`dispatch`、`getNextDag()` |
| `Fog-Computing-multiDeviceDebug/src/mengxu/taskscheduling/TaskOption.java` | 处理器引用、计算/上传/下载时间、readyTime、priority、`priorTo()` |
| `Fog-Computing-multiDeviceDebug/src/mengxu/taskscheduling/Process.java` | 开始时间、完成时间及一次执行的含义 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/taskscheduling/Server.java` | 等待队列、readyTime、资源参数 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/taskscheduling/JobType.java` | DAG 与链式工作流分支 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/taskscheduling/ServerType.java` | EDGE 和 CLOUD 类型 |

**完成标准：** 能解释“一个 Job 有多个 Task；一个 Task 有多个 TaskOption；选中一个 TaskOption 后形成一次 Process”。

第一次读 `Task` 时可先跳过为多个基准算法计算 rank 等量的方法。

### 第 4 步：理解全局状态和事件循环

| 文件所在路径 | 阅读重点 |
| --- | --- |
| `Fog-Computing-multiDeviceDebug/src/mengxu/simulation/state/SystemState.java` | 时钟、设备、服务器、系统内/已完成工作流、计数和重置 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/simulation/DynamicSimulation.java` | 构造函数、`setup()`、`mobiledeviceHaveEvent()`、`run()` |
| `Fog-Computing-multiDeviceDebug/src/mengxu/taskscheduling/MobileDevice.java` | 先读队列、readyTime、`addEvent()`、规则设置和状态方法 |

**完成标准：** 能描述“收集设备事件 → 弹出最早事件 → 更新时钟 → 调用 trigger → 收集新事件”的循环。

这里的并行执行主要由模拟时间和事件队列表示，不需要给每个设备开启真实线程。

### 第 5 步：按生命周期精读四种事件

| 阅读次序 | 文件所在路径 | 阅读重点 |
| --- | --- | --- |
| 1 | `Fog-Computing-multiDeviceDebug/src/mengxu/simulation/event/AbstractEvent.java` | 时间、设备引用、抽象 `trigger()` 和比较接口 |
| 2 | `Fog-Computing-multiDeviceDebug/src/mengxu/simulation/event/JobArrivalEvent.java` | 工作流到达、入口任务、路由决策、后续工作流生成 |
| 3 | `Fog-Computing-multiDeviceDebug/src/mengxu/simulation/event/TaskVisitEvent.java` | 上传后到达、就绪时间、直接执行或排队 |
| 4 | `Fog-Computing-multiDeviceDebug/src/mengxu/simulation/event/ProcessStartEvent.java` | 占用资源、设置 readyTime、产生完成事件 |
| 5 | `Fog-Computing-multiDeviceDebug/src/mengxu/simulation/event/ProcessFinishEvent.java` | 标记完成、选择等待任务、释放后续就绪任务、工作流完成 |

论文的 `WorkflowArrivalEvent` 对应这里的 `JobArrivalEvent`。

**完成标准：** 每种事件都能说明“读取哪些状态、修改哪些状态、调用哪条规则、产生哪些事件”。

除了 `trigger()`，还要看构造函数和 `compareTo()`：有些状态修改在构造函数中完成，同一时间的事件顺序也会影响模拟行为。

### 第 6 步：理解路由与排序规则接口

| 文件所在路径 | 阅读重点 |
| --- | --- |
| `Fog-Computing-multiDeviceDebug/src/mengxu/rule/RuleType.java` | ROUTING 与 SEQUENCING |
| `Fog-Computing-multiDeviceDebug/src/mengxu/rule/AbstractRule.java` | `nextTaskOption()`、`priorTask()`、`priority()` |
| `Fog-Computing-multiDeviceDebug/src/mengxu/algorithm/FCFS.java` | 最简单的具体规则及其两种用途 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/taskscheduling/TaskOption.java` | 回看 `priorTo()` 的评分方向和平分规则 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/simulation/DecisionSituation.java` | 决策情境的基础接口 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/simulation/RoutingDecisionSituation.java` | 执行选项和系统状态 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/simulation/SequencingDecisionSituation.java` | 等待队列、处理器和系统状态 |

**完成标准：** 能独立用 Python 写出两类“计算候选分数并选择”的函数，保留平分行为。

此处评分较小者优先；FCFS 排序使用工作流发布时间，不是任务入队时间。

**到这里可开始第一版 Python 小模拟器，不必等待 GP 部分。**

### 第 7 步：理解工作流和随机实例生成

| 文件所在路径 | 阅读重点 |
| --- | --- |
| `Fog-Computing-multiDeviceDebug/src/mengxu/taskscheduling/MobileDevice.java` | `generateWorkflowJob()`、`setup()`、`completeJob()` |
| `Fog-Computing-multiDeviceDebug/src/mengxu/taskscheduling/WorkflowParser.java` | XML 中任务和父子依赖的解析 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/taskscheduling/dag/DAGType.java` | 工作流模板编号 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/taskscheduling/dag/DAGTypePath.java` | 当前调用的 `getDAGTypePathForSubmit()` |
| `Fog-Computing-multiDeviceDebug/src/mengxu/util/random/AbstractRealSampler.java` | 实数采样器接口 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/util/random/AbstractIntegerSampler.java` | 整数采样器接口 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/util/random/UniformSampler.java` | 实数均匀采样 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/util/random/UniformIntegerSampler.java` | 整数均匀采样及端点 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/util/random/ExponentialSampler.java` | 工作流到达间隔 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/util/random/BandwidthCloudSampler.java` | 云带宽离散分布 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/util/random/BandwidthEdgeSampler.java` | 边缘带宽 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/util/random/TwoSixTwoSampler.java` | 工作流权重采样 |

运行时 XML 目录为 `Fog-Computing-multiDeviceDebug/dax/`，例如：

- `Fog-Computing-multiDeviceDebug/dax/CyberShake_30.xml`
- `Fog-Computing-multiDeviceDebug/dax/Epigenomics_24.xml`
- `Fog-Computing-multiDeviceDebug/dax/Inspiral_30.xml`
- `Fog-Computing-multiDeviceDebug/dax/Montage_25.xml`
- `Fog-Computing-multiDeviceDebug/dax/Sipht_30.xml`

当前代码使用 `./dax/...` 相对路径，因此运行工作目录应设为项目根目录。类中其他旧路径不能直接当作当前生效路径。

**完成标准：** 能解释 DAG 来源、任务参数来源、到达时间和每个执行选项的时间计算。

注意：这里的 DAX 解析器主要读取任务与依赖；工作量、数据量随后随机赋值，不能直接把 XML 原始 runtime 等字段当作实际模拟输入。

### 第 8 步：理解 GP 规则树求值和特征

| 文件所在路径 | 阅读重点 |
| --- | --- |
| `Fog-Computing-multiDeviceDebug/src/mengxu/rule/evolved/GPRule.java` | `priority()`、`readFromLispExpression()` |
| `Fog-Computing-multiDeviceDebug/src/mengxu/gp/CalcPriorityProblem.java` | 将候选执行选项和系统状态提供给树 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/gp/data/DoubleData.java` | 树求值中的数值结果载体 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/gp/terminal/JobShopAttribute.java` | `value()`、`relativeAttributes()` 和特征定义 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/gp/terminal/AttributeGPNode.java` | 特征叶节点求值 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/gp/terminal/TerminalERC.java` | 终端节点包装 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/gp/terminal/TerminalERCUniform.java` | 初始化和变异时选择终端 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/gp/function/Add.java` | 加法及递归求值模式 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/gp/function/Sub.java` | 减法 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/gp/function/Mul.java` | 乘法 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/gp/function/Div.java` | 受保护除法 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/gp/function/Max.java` | 最大值 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/gp/function/Min.java` | 最小值 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/util/lisp/LispParser.java` | 将表达式解析为树 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/util/lisp/Tokenizer.java` | 表达式分词，按需读 |

当前配置的函数集合是加、减、乘、除、max、min。存在 `If.java` 不表示当前实验启用了它。

建议建立特征对照表：

| 特征 | 当前实现中的主要含义 |
| --- | --- |
| NIQ | 候选处理器等待队列的任务数量 |
| WIQ | 等待队列中任务的计算时间总和 |
| MRT | 处理器 readyTime；当前代码直接取该值 |
| TTIQ | 等待队列中计算、上传与下载时间总和 |
| UT / DT / PT | 当前执行选项的上传、下载与计算时间 |
| TWT | 当前时钟减任务选项的 readyTime |
| TIS | 当前时钟减工作流发布时间 |
| NTR | 工作流任务总数减已完成任务数 |

**完成标准：** 同一决策状态和表达式下，Python 与 Java 算出相同特征值、规则分数，并选中相同候选项。

此阶段可先用 Python 函数或小型树解释器执行固定表达式；不必同时实现演化。

### 第 9 步：理解个体评估、重置和训练实例轮换

| 文件所在路径 | 阅读重点 |
| --- | --- |
| `Fog-Computing-multiDeviceDebug/src/mengxu/ruleoptimisation/RuleOptimizationProblem.java` | 基础问题接口 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/ruleoptimisation/MultipleTreeRuleOptimizationProblem.java` | `setup()`、`evaluate()`：个体树转为规则 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/ruleevaluation/AbstractEvaluationModel.java` | 评估模型接口 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/ruleevaluation/MultipleRuleEvaluationModel.java` | `setup()`：场景、实例数、重复次数、模拟器配置 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/ruleevaluation/MultipleTreeMultipleRuleEvaluationModel.java` | `evaluate()`：运行、平均指标、异常运行处理 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/taskscheduling/SchedulingSet.java` | 模拟器集合、重复评估及 seed 轮换 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/taskscheduling/Objective.java` | 目标函数类型 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/simulation/DynamicSimulation.java` | 回看 `reset()`、`rerun()`、`rotateSeed()`、`makespan()` |
| `Fog-Computing-multiDeviceDebug/src/mengxu/taskscheduling/MobileDevice.java` | 回看完成计数和记录条件 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/simulation/state/SystemState.java` | 回看工作流加入、记录边界与重置 |

多树个体中：`trees[0]` 为排序规则，`trees[1]` 为路由规则。单树分支以唯一树作为路由规则，并在评估模型中配固定 FCFS 排序规则。

**完成标准：** 能说明“一个个体如何得到适应度、不同个体如何使用训练实例、何时重置、何时切换 seed、哪些工作流进入统计”。

不能把 `reset()`、`rerun()` 和 seed 轮换当成同一操作。

### 第 10 步：理解并复现 GP 演化

| 文件所在路径 | 阅读重点 |
| --- | --- |
| `Fog-Computing-multiDeviceDebug/src/mengxu/gp/GPRuleEvolutionState.java` | 基础初始化、终端集合及演化支持 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/algorithm/multipletreegp/GPRuleEvolutionStateBaseline.java` | `evolve()`：评估、统计、繁殖和实例轮换 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/algorithm/multipletreegp/AllIndexAllSwapCrossoverPipeline.java` | 一棵树做子树交叉，另一棵树做整树交换；复制与深度限制 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/algorithm/multipletreegp/SimpleStatisticsSaveRulesizeGen.java` | 最优规则和树大小记录 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/algorithm/multipletreegp/multipletreegp-dynamicBaseline.params` | 再次精读全部生效参数 |

按需进入 ECJ：

| 文件所在路径 | 用途 |
| --- | --- |
| `Fog-Computing-multiDeviceDebug/src/ec/gp/GPIndividual.java` | 个体结构 |
| `Fog-Computing-multiDeviceDebug/src/ec/gp/GPTree.java` | 树结构 |
| `Fog-Computing-multiDeviceDebug/src/ec/gp/GPNode.java` | 节点、复制和替换 |
| `Fog-Computing-multiDeviceDebug/src/ec/gp/koza/HalfBuilder.java` | 初始树生成 |
| `Fog-Computing-multiDeviceDebug/src/ec/select/TournamentSelection.java` | 锦标赛选择 |
| `Fog-Computing-multiDeviceDebug/src/ec/gp/koza/KozaNodeSelector.java` | 交叉、变异中的节点选择 |
| `Fog-Computing-multiDeviceDebug/src/ec/gp/koza/MutationPipeline.java` | 子树变异 |
| `Fog-Computing-multiDeviceDebug/src/ec/simple/SimpleBreeder.java` | 繁殖及精英保留 |
| `Fog-Computing-multiDeviceDebug/src/ec/simple/SimpleEvaluator.java` | 种群评估 |
| `Fog-Computing-multiDeviceDebug/src/ec/breed/ReproductionPipeline.java` | 复制繁殖 |
| `Fog-Computing-multiDeviceDebug/src/ec/multiobjective/MultiObjectiveFitness.java` | 当前适应度存储与比较 |

若 GP 框架仍不好理解，可阅读包内教程：

- `Fog-Computing-multiDeviceDebug/src/ec/app/tutorial4/MultiValuedRegression.java`
- `Fog-Computing-multiDeviceDebug/src/ec/app/tutorial4/tutorial4.params`
- `Fog-Computing-multiDeviceDebug/src/ec/app/tutorial4/Add.java`

**完成标准：** 能说明一代演化的完整过程，并在 Python 中显式实现相同的双树含义、算子、深度限制、精英保留和评估机制。

### 第 11 步：最后阅读测试和结果分析

| 文件所在路径 | 用途 |
| --- | --- |
| `Fog-Computing-multiDeviceDebug/src/mengxu/ruleanalysis/MultipleTreeRuleTest.java` | 多树规则测试流程 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/ruleanalysis/MultipleTreeResultFileReader.java` | 读取训练输出中的规则 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/ruleanalysis/TestResult.java` | 测试结果记录 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/ruleanalysis/BaselineRuleTest.java` | 基准规则测试 |
| `Fog-Computing-multiDeviceDebug/src/mengxu/algorithm/HEFT.java` | 一个基准算法的路由与排序逻辑 |

其他基准算法在 `Fog-Computing-multiDeviceDebug/src/mengxu/algorithm/` 中，按实验需求读取。

单树对照配置为：

`Fog-Computing-multiDeviceDebug/src/mengxu/algorithm/singletreegp/multipletreegp-dynamicSingle.params`

**完成标准：** 能使用独立测试实例评估规则，区分训练适应度与测试表现，并核对论文参数。

## 6. 调试和阅读技巧

### 6.1 逐行执行的适用范围

适合逐行执行：一个任务的生命周期、一次规则选择、一个特征计算、一次树求值、一个小型交叉或变异。

不适合从头逐行执行：完整训练程序、整个 ECJ 初始化、全部日志和文件输出。

使用 Step Over 跳过已理解的方法；用 Step Into 进入状态修改、时间计算和决策方法；用条件断点限制在指定工作流或任务上。

### 6.2 第一个调试例子

使用一个移动设备、一个服务器、一个工作流和两个任务 A → B。固定到达时间、工作量、数据量、带宽和处理速率，并固定规则。

推荐断点位置：

1. `DynamicSimulation.run()` 中弹出事件后。
2. 四种事件的 `trigger()`。
3. `AbstractRule.nextTaskOption()` 和 `priorTask()`。
4. `Task.getNextDag()`。
5. `MobileDevice.completeJob()`。
6. `DynamicSimulation.makespan()`。

观察：系统时钟、任务 ID、处理器 ID、事件时间、两类队列、readyTime、complete、dispatch、已完成工作流数量。

### 6.3 每个方法只记录四类信息

| 项目 | 记录内容 |
| --- | --- |
| 输入 | 参数及对象 |
| 读取 | 哪些状态用于判断或计算 |
| 修改 | 哪些对象、字段、队列发生变化 |
| 结果 | 返回值、决策、新事件或指标 |

先写语言无关的伪代码，再写 Python。若不能说明哪些对象被修改，说明尚未理解到可移植程度。

### 6.4 阅读记录模板

```markdown
### 方法或事件名称
- Java 文件路径：
- 论文对应位置：
- 输入：
- 读取的状态：
- 修改的状态：
- 返回值或新事件：
- 时间计算：
- 平分或边界处理：
- Python 实现思路：
- 对照用例：
- 未解决问题：
```

## 7. Python 实现阶段与验收标准

| 阶段 | 实现内容 | 进入下一阶段前的标准 |
| --- | --- | --- |
| A | 数据模型、固定输入、事件队列、简单规则 | 两任务工作流可完整运行，时间可手算核对 |
| B | DAG 就绪判断、两类决策、等待队列 | 链式和分叉汇合实例的 Java/Python 轨迹一致 |
| C | DAX、多设备、随机实例、统计、重置 | 固定实例可重复运行，多设备共享资源行为正确 |
| D | 十个特征、六个函数、固定 GP 表达式 | 特征、规则分数、候选选择一致 |
| E | GP 初始化、选择、交叉、变异、精英保留 | 小规模演化可运行，算子语义与评估机制已核对 |
| F | 正式场景、基准算法和重复测试 | 核对论文配置并复现主要统计趋势 |

完成阶段 D 后，就能在 Python 中执行 Java 导出的 GP 调度规则，是可用的中间成果。

Python 模块可按 model、instance、events、simulation、rules、features、gp、experiments 划分。不要为迁移而完整复制 ECJ 的继承体系。

使用现成 Python GP 库前，逐项核对双树表示、节点选择概率、受保护除法、深度约定、树交换交叉、复制语义和实例轮换机制。

## 8. 迁移时必须核对的行为

### 8.1 评分方向与平分处理

`TaskOption.priorTo()` 中评分较小者优先，平分后比较工作流发布时间、设备 ID、工作流 ID。完全相同时还需保留候选遍历行为。

不可直接写 argmax，也不可随意加任务 ID 或服务器 ID 作为新的平分键。

### 8.2 上传、计算、下载与资源释放

当前 `Process` 的完成时间：

```text
finish_time = start_time + processing_time + download_delay
```

开始事件把处理器 readyTime 设为上述时间。因此当前代码把下载时间纳入处理器再次可用的时间。

不要在复现时自动改成“计算结束释放处理器，下载另行进行”。若要探索这种模型，应在对照基线完成后单独修改。

### 8.3 同时刻事件顺序

各事件类实现了自己的 compareTo，不能只按时间排序。部分比较结果相等，Java PriorityQueue 不保证稳定顺序。

Python 的“时间 + 递增编号”堆键会增加稳定顺序。应先核对原比较逻辑，并专门构造同时刻事件例子；严格轨迹对照需要关注两种堆实现处理平分的差异。

### 8.4 随机数与实例来源

相同 seed 不等于相同实例。初期固定或导出 DAG、所属设备、到达时间、任务工作量、数据量、资源参数，再分别提供给 Java 与 Python。

需要特别注意按事件推进时生成后续工作流的采样调用顺序。最终 makespan 不同，可能来自输入已不同，而不是调度代码错误。

### 8.5 数值与树求值

除法是受保护除法：通常零分母返回 1，而不是抛异常。

若需要严格数值一致，还应核对 Java Double.compare 对正负零、NaN 的行为，以及无穷值传播、溢出、最大最小函数行为。初期先处理普通有限数值与零分母，再补边界用例。

### 8.6 状态共享与复制

同一个 Task 在候选执行选项、工作流和事件中应保持正确共享。不要在转换时随意复制成多个互不关联的任务。

GP 子代则需要正确复制树，不能因浅复制意外修改父代。Python dataclass 默认按字段比较对象，是否适用也应明确决定。

### 8.7 warm-up、终止与异常运行

不能直接把 warmupJobs 理解成“删掉前若干个完成工作流”。要联合核对工作流发布、记录条件、完成计数和模拟停止条件。

训练与测试中的异常运行处理也应分别阅读：评估模型和规则测试调用链不完全相同，不可统一改成自己认为合理的处理方式而不记录。

### 8.8 配置与论文差异

当前多树配置种群大小 100，论文表 VI 为 1000。其他参数也应逐项核对。

建议记录：

| 项目 | 论文设定 | 当前代码或配置 | 复现采用值 | 原因 |
| --- | --- | --- | --- | --- |
| 种群大小 | 1000 | 多树配置为 100 | 调试先用小规模，正式实验核对为 1000 | 控制调试成本 |
| warm-up | 见论文场景表 | 需联合检查计数和筛选逻辑 | 核对后填写 | 避免误读名称 |
| 同时刻事件 | 论文描述不足以替代源码细节 | 各事件 compareTo | 核对后填写 | 保留决策行为 |

不要一边移植，一边悄悄修正疑似问题。记录差异、建立基线，再做独立修正版本。

## 9. 验证顺序与用例

### 9.1 从局部到整体

1. 同一状态下的特征值。
2. 同一表达式的规则分数。
3. 选中的执行选项或等待任务。
4. 事件时间、类型和状态变化。
5. 每个任务的开始与完成时间。
6. 工作流完成时间和 makespan。
7. GP 算子和评估流程。
8. 随机实验分布与论文趋势。

不一致时定位第一个不同的决策或事件。浮点时间采用合理的绝对、相对容差；ID、状态和选择结果精确比较。

### 9.2 最少准备的例子

| 用例 | 检查目的 |
| --- | --- |
| 一个无依赖任务 | 基本生命周期 |
| A → B | 后继就绪与时间计算 |
| A → B/C → D | 分叉、汇合和避免重复派发 |
| 多任务竞争一个处理器 | 排队、排序与释放 |
| 多个同时刻事件 | 事件比较和平分 |
| 本地与远程执行 | 上传下载语义 |
| 多设备共享服务器 | 共享队列、事件所属设备 |
| 一实例重复评估 | 重置是否完整 |
| 零分母规则 | 受保护除法 |
| 小型 warm-up 场景 | 计数、统计和终止 |

建议日志字段：时钟、事件类型、工作流 ID、任务 ID、设备/服务器 ID、候选分数、选择结果、readyTime、队列和新事件。

## 10. 第一轮实践安排

按掌握情况推进，不要以固定天数代替验收。

| 顺序 | 本轮工作 | 可检查成果 |
| --- | --- | --- |
| 1 | Java 基础与 IDE 调试 | 任务类和两个事件子类的小程序 |
| 2 | 阅读第 1～3 步 | 模型关系和最小运行流程 |
| 3 | 阅读第 4～6 步 | 一个任务完整轨迹及两类规则说明 |
| 4 | Python 固定小实例 | 两任务模拟器及手算结果 |
| 5 | Java/Python 对照 | 事件和决策比较记录 |
| 6 | 阅读第 7 步并扩展 | DAG、多设备、实例和统计 |
| 7 | 阅读第 8 步 | 固定 GP 规则的 Python 执行 |
| 8 | 阅读第 9～11 步 | 评估、演化和独立测试 |

如果尚不能解释等待队列和资源可用时间，不进入 GP 训练。GP 调用模拟器次数很多，底层误差会放大为难以定位的结果差异。

## 11. 可选扩展研究的前提

满足以下条件后，再探索新特征、新规则、演化算子或通信模型：

- 固定输入和规则的模拟行为经过对照。
- 特征与表达式求值经过验证。
- GP 算子、配置和测试机制有明确记录。
- 能区分原始实现、论文复现设置和自己的改动。

保留基线配置、实例、规则表达式和结果。一次改变一个因素，使用相同测试实例对照；避免同时改变模型、特征和训练设置。

## 12. 最小行动清单

- [ ] 补 Java 类、继承、多态、集合和引用语义。
- [ ] 配置 JDK、IDE、src 和 libraries，并从源码运行。
- [ ] 快速读入口与多树配置，不深入整个 ECJ。
- [ ] 读 Job、Task、TaskOption、Process、Server。
- [ ] 读全局事件循环和四类事件。
- [ ] 跟踪一个固定小工作流。
- [ ] 用 Python 实现固定规则的小模拟器。
- [ ] 对照同一输入的事件和决策。
- [ ] 扩展 DAG、多设备、实例生成和统计。
- [ ] 复现特征与固定 GP 规则求值。
- [ ] 读适应度评估、重置、轮换和 GP 算子。
- [ ] 小规模训练通过后，再开展正式论文实验。

## 13. 参考材料

主要依据：

1. 上传代码包：Fog-Computing-multiDeviceDebug.zip。
2. 上传中英对照论文：Xu 等 - 2023 - Genetic Programming for Dynamic Workflow Scheduling in Fog Computing.zh-CN.dual.pdf。重点对应第 IV 节问题模型、第 V 节模拟器、第 VI 节 MTGP、第 VII 节实验，以及算法 1、算法 2、表 II、表 V、表 VI。

辅助资料：

- [Java PriorityQueue 官方文档](https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/util/PriorityQueue.html)：排序与平分行为。
- [Python heapq 官方文档](https://docs.python.org/3/library/heapq.html)：Python 事件队列实现。
- [ECJ 官方文档与教程](https://people.cs.gmu.edu/~eclab/projects/ecj/docs/)：GP 框架；优先对照代码包中携带的实现版本。

