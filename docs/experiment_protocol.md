# 公共危机 Agent 研究：实验协议

> 文件用途：确定研究问题、实验格点、对比、统计计算与报告边界。动力学规则和基础配置见 `model.md`。本协议不代替 Pilot、独立接受、正式模拟或真实系统验证的运行证据。正文主要问题只有三个；敏感性不另立研究问题。

## 1. 总问题、研究问题与证据性质

总问题：**在信息不完备、任务时限紧迫和处理能力受限的城市应急系统中，局部Agent失效怎样经由业务与技术依赖形成关键公共功能风险；监测处置、指挥配置和人机决策的有效边界在哪里？**

- **RQ1：系统脆弱性与关键公共功能风险。** 检查同等受影响节点数量是否足以描述公共后果，以及共同依赖怎样改变损失分布。
- **RQ2：信息不完备、风险展开与监测处置。** 检查异常可见阶段、集中/逐步暴露如何改变隔离效果，并列报告处置负担。
- **RQ3：时间压力下的指挥配置与人机决策。** 检查审核能力、分诊、信息等待和附加指挥复核的条件性效果。

本研究是明确假设下的机制计算，不是现实概率预测，也不是现实政策因果识别。参数从文献得到动机而非数值校准。所有null、反向、结构性零和不确定结果都保留；不得根据模拟结果改seed、挑位置、改权重、删对照或换主图切片。

## 2. 科学规格的唯一来源

基础常数、节点、边和功能成员仅由 `configs/base.yaml` 维护；本协议不复制它们。本文附录A是实验格点、种子和评分视图的唯一机器可读定义；正文规定其解释和展开规则。`study.build_catalog()` 在每次运行开始时生成一次内存中的实验设计，供执行、统计和展示直接使用。

每个family只做两步：基础配置覆盖`fixed`，再取`axes`的笛卡尔积。一个axis元素可以是列表，例如`initial_nodes: [[A04],[A08]]`；它表示一个参数的完整取值，不再展开列表内部。family顺序、字典插入顺序不得影响配置身份。

`select`是**基础配置上的完整确定补丁**，不是根据结果查询的筛选语言。每个primary term解析后必须命中已由family生成的配置；命不中是规格错误，不能在Formal后补生成需要的参照。

### 2.1 显式外生情景

| 实验部分 | 初始节点故障 | 共同资源冲击 |
|---|---|---|
| RQ1位置 | A01—A30逐个单点 | 无 |
| RQ1共同依赖 | 空集合 | 指定一种资源、p、K与partition |
| RQ2观察/隔离/检测 | 空集合 | data、同一固定中心组结构；仅改变已注册因素 |
| RQ2消息核验 | 指定代表节点之一 | 无 |
| RQ3全部主实验与敏感性 | A04 | 无 |

表中情景在附录中都有字段，不能靠旧仓库默认继承。RQ3不代表所有故障位置；位置差异由RQ1负责。全部实验始终启用相同正常信息与错误传播机制。

### 2.2 避免把不同治理机制的作用绑在一起

RQ1、RQ2以及RQ3的人工审核、分诊、信息等待主比较，默认不设置额外指挥gate。指挥主比较首先在无人工审核条件下运行；只在预定中心处叠加人工审核作为敏感性。这样减少“人工排队+指挥排队”的隐含混杂，而不是临时关闭正常信息世界。

无人工审核不等于没有本地核验、没有内部信息，也不等于关闭信息不足误差。它仅取消指定人工服务。

## 3. 主结果、评分视图与报告层次

### 3.1 唯一主结果

主结果是七项公共功能的关键性加权累计服务能力缺口`L`，按`model.md`的主成员权重、主功能关键性、hard时限评分和主受损效用计算。

主结果不是伤亡、资金损失或公共危机等级。节点服务到功能的线性映射是模型假设；不得把由权重定义导致的位置差异称为独立发现了现实因果机制。

单项功能 `L_f` 的单位为“归一化服务缺口 × 抽象tick”；总 `L` 为“功能关键性 × 抽象tick”。单位标签不改变任何数值公式。

### 3.2 评价敏感性只重算，不重新模拟

附录的`evaluation_views`只影响计量：成员等权、节点关键性加权、功能等权、linear_grace、受损效用上下值。它们使用同一run中的四个30维积分重算，不能作为simulation config维度，也不能改变分诊排序。视图中`compromised_utility: base`引用基础配置的唯一主值，只有上下敏感性视图另给数值，不手写第二个主值。

**全部主效应**都披露七项功能方向；均值效应使用各功能均值差，ES95效应则按§9.1的同一总损失尾部进行功能贡献分解，不能把各功能自己的ES95相加。其中生命安全分诊必须同步显示其他功能是否受损。所有主结果再按grace、等功能关键性、受损效用上下值重算。位置R²另外重算成员等权和节点关键性映射。其余大量辅助效应只发布主视图，避免无消费者的笛卡尔扩张。

### 3.3 次级与机制指标

次级风险指标包括尾部损失ES95、主mapping阈值失效时长、曾受损节点数、外部错误动作数。成本包括互斥阻塞分解、核验/审核/指挥服务请求量以及误隔离/误拒绝。信息指标区分已接受覆盖与真实正确比例。

`critical_review_queue_time`是机制诊断，不是独立福利结果。`unfinished_tasks`和`active_harms_at_horizon`用于揭示有限窗口截尾。不得把所有指标再加权成一个“综合最佳治理分数”。

另报告非补偿性次级结果 `worst_function_deficit = max(F1,...,F7)`：先在每个run取七项归一化功能缺口的最大值，再求均值及配对差，单位为归一化服务缺口 × 抽象tick。它不同于“七项均值的最大值”，不乘功能关键性，不改变主结果L。仅从同一raw积分的主评价视图派生，不新增模拟配置。fixed-budget、审核容量、分诊及共同依赖partition的报告同时展示F1–F7方向和这个次级结果；总L改善不能代替功能间取舍。

## 4. 假设、主估计量与可证伪范围

文献支持研究关系，不规定本合成系统必须出现某个方向。除位置预测量外，主估计量都为预先规定线性对比；其精确配置由附录`primary_effects`给定。正文下式仅用于解释。

| 编号 | 主问题 | 主估计量 | 不允许的解释 |
|---|---|---|---|
| H1a | 同一受影响数量是否足够 | 主mapping的交叉拟合增量R² | 现实因果位置效应、对未见过的新位置外推 |
| H1b | 共同依赖是否重塑均值/尾部 | 固定data情景K2−K1的均值差和ES95差 | 分散一定优越、显著比例是现实发生概率 |
| H2a | 前移持续监测窗口是否改变处置效果 | `Δiso(O2)−Δiso(O0)`，固定同期暴露 | 等检测预算的纯时点效应、以两个单点显著与否代替交互 |
| H2b | 暴露节奏是否改变隔离效果 | `Δiso(progressive,O2)−Δiso(abrupt,O2)` | 完整渐发危机理论、实际受损集合完全相同 |
| H3a | 审核的时间和容量边界 | 审核效应d2−d10；d5时cap1−cap3 | 人优于AI或AI优于人 |
| H3b | 优先配置是否改变公共后果 | d5、cap1下life_safety−FIFO | 目标对齐自动验证最佳领导方式 |
| H3c | 附加指挥检查的时限边界 | centralized−distributed之效应在d2与d10的差 | 等资源纯集中化效应、个人领导力 |
| H3d | 信息等待的净效果边界 | integrated−fast之效应在d2与d10的差，无人工审核 | 更多信息有价值这个预置函数本身是发现 |

令`Δhuman(d,c)=E[L(full,d,c)]−E[L(autonomy,d)]`。容量交互中同一个autonomy参照出现两次，会代数抵消；实现必须先合并同cell系数，再计算与bootstrap，不能伪造两份独立参照。

位置R²加附录九项线性主效应，构成报告的有限主估计量集合。其余预先规定直接比较、OFAT与额外分组均为次级或敏感性，不能因结果醒目而升级。

## 5. RQ1设计及估计细节

### 5.1 位置：30条物理配置，而非三种评分各跑一套

逐个设置一个初始节点错误，其他条件相同；三种成员mapping来自同一组轨迹。位置比较使用“曾受损节点数K”，包括信息不足引起的额外错误，**不称为纯粹由种子引发的传播后代数**。

每个run index对应全部30个位置配置的共同随机场。固定分为偶数/奇数两折；同一run index在所有位置中必须属于同一折，以避免潜在场景泄漏。

训练折模型均为分组均值，不增加回归库或调参：

- 基线预测`m0(K)`：训练样本中同K的平均损失；该K未出现时退回训练折全体均值。
- 扩展预测`m1(K,s)`：训练样本中同K、同初始位置s的平均损失；无该组合时退回`m0(K)`。

在另一折评分，再交换训练/测试。合并两折：

$$\Delta R^2=\frac{SSE_0-SSE_1}{SST},\qquad SST=\sum_{test}(Y-\bar Y_{train})^2.$$

每条测试记录的参考均值取其对应训练折均值。不得用全体数据拟合后再称held-out，不得裁剪负增量。`SST=0`时记`undefined`并保留原因。该量回答已知30个位置的新模拟抽样中位置是否增加预测信息；对K作条件化是描述性比较，不能解释为切断级联途径之后的因果直接效应。

Bootstrap在原两折内按run index簇重抽样，每个抽中的index携带所有30位置，重新拟合并重新评价。不能独立重抽每个位置，也不能仅重抽已经得到的预测残差。若点估计分母为0，不计算其CI；若点估计有定义但任一重抽样分母为0，保留点估计，CI标为undefined并报告有效次数，不删除这些重复后冒充无条件95%区间。

### 5.2 位置图的固定选择规则

图中同规模示例只用于解释，不替代全体主估计。候选`K>1`，要求至少两个位置各有20条记录；选合格位置的总样本量最大的K，并列选较小K。展示该K所有达到20条的位置，按Agent ID排序，不按损失排序。无合格层则显示“无满足支持量的同规模示例”，不能换seed或降低门槛。

`position_strata.csv`保存所有K/位置的样本数和均值，未观察组合不伪造0；`position.csv`保存主量、两种映射敏感性、分母状态和有效bootstrap次数。图中组均值若没有另行正确bootstrap，只画点与样本量，不假装拥有置信区间。

### 5.3 共同依赖

附录给出资源类型、四档p、五档K以及额外四个partition。默认分组按`model.md`算法生成；额外partition仅用于K2和指定两档p。每组是否故障独立，但组内潜在暴露相关。

对基准partition，登记K相邻对比：K2−K1、K3−K2、K5−K3、K10−K5。额外K2 partition统一对照同资源、同p的基准K1，不引用不存在的“同seed K1 cell”；K1成员完全相同时复用。

均值差与ES95差分别计算。不得为了比较尾部，把损失差的ES95误当成两个分布的ES95之差。model/data/tool用户集合与失效注入点不同，所以资源类别之间不作无条件强弱排名。

## 6. RQ2设计及完整对照

### 6.1 观察阶段×隔离×暴露展开

固定同一data资源情景，无初始节点错误。登记每种暴露、每个O下`isolation−no_isolation`；同一O与隔离状态下`progressive−abrupt`；再按§4登记两项主交互。另在progressive下的观察交互、O0下的暴露交互为次级，不能事后选择。O改变的是监测机会（包括误报机会），不把观察次数不同的对比写成等次数下的纯检测灵敏度效应。

O0/O1/O2保留为完整持续监测政策：窗口前移也增加累计检测和误报机会。其结果只能解释为**前移持续监测窗口的整体政策效果**，不能单独识别固定监测资源下提前检查的作用。

无隔离时O没有治理消费者，因此若规范化后多个配置完全相同，复用同一模拟。保留相应结构性零对比，不把重复role当成独立证据。

### 6.2 检测与误报

每个暴露方式分别运行灵敏度与误报率的3×3监测隔离网格。每个cell相对同暴露、无隔离、中心检测参数的配置计算组合效应。另固定其他因素登记相邻检测概率对比与相邻误报率对比。

这些敏感度/误报组合是独立情景条件，不是从同一个检测器ROC曲线上估计出来的工作点。不得称某个格点是现实可用检测器的最优阈值。

### 6.3 消息核验

五个代表初始节点及额外质量切片在附录写死。对每个节点登记critical−none、global−none、critical−global；对A04在critical和global内分别登记中心与上下两档的相邻质量对比。none下质量参数无行为消费者，不生成多次相同模拟。

核验负荷对覆盖范围内所有新消息计数。它不含时间与金钱，故“损失下降但核验工作量增加”不能被写成经过社会成本权衡后的净福利结论。

### 6.4 固定监测预算下的时点补充实验

本补充实验属于RQ2，解决持续监测时点与累计检查次数同时变化的识别缺口，不新增RQ，也不替换§6.1。外生情景固定为该实验的中心data冲击：无初始错误、同期暴露、中心概率与单组基准partition；检测概率、误报率和其他条件均保持基础中心值，自动隔离开启，指挥为distributed。

附录 `fixed_budget` 的 `monitoring_offset` 依次定义early、middle、late。每个Agent仅在 `t=release+offset` 的监测阶段获得一次主动检测机会，不以方案形成/行动完成为门槛；“release后第1个tick”明确为release+1，不含release当tick。合法窗口为 `0 <= t < horizon`；目标不在窗口则不检查、不补到尾部、不顺延。统计实际 `monitoring_requests`，不得机械假定每run恰好30次。在本固定中心窗口中如全部目标合法，三组每节点检查次数应完全相同。检测与误报分别使用节点任务的一次潜在随机数，三时点保持CRN；当前真异常仍由当时状态决定，不能要求三组告警数相同。

运行前规定三项方向：**middle−early、late−early、late−middle**。均值ΔL为本补充实验的主要输出；ES95差及其总L同尾部功能贡献为次级。每项还披露F1–F7均值差、最大单项功能缺口均值差、真检测、误隔离、实际检查请求数、曾受损节点数和外部错误动作；三组同时报告这些量的水平。使用既有run-index簇bootstrap，不新增评分、切片、seed或检测质量条件。允许解释为**检测次数受控时的监测时点效果**，包括提前隔离及恢复对后续传播和服务的影响；不等于持续监测政策效果，更不是现实政策因果估计。

## 7. RQ3设计、交互和敏感性

### 7.1 人工能力与任务分诊

主人工比较跨三个到期宽度、有限及无限容量，其他参数固定。每个full cell对照同外生情景、时限、信息政策、指挥结构和异常执行倾向的autonomy cell。

分诊比较在有限两档容量和三个时限下运行FIFO、due_first、life_safety。登记due_first−FIFO、life_safety−FIFO的直接效果，另登记d5下两种分诊效果的cap1−cap3交互作为次级。不得以队列先后调整直接称为完整领导理论检验。

审核灵敏度、特异度、服务时长分别按附录作OFAT，中心配置复用。只比较单一字段变化；普通审核与“读取潜在真值后完美行动”必须分开，完美审核仅是验证夹具。

### 7.2 指挥配置

主指挥比较在autonomy下，跨时限比较selective−distributed、centralized−distributed以及centralized−selective。另在d5加入full背景，检查人工与指挥串联的中心情景。

指挥容量×纠错有效性的有限敏感性在d5、autonomy下运行。包含零纠错效能作为消融；不得要求其必然使损失上升，因为等待也可能让后续信息赶到，从而改变风险。该消融用于解释组成机制，不是通过方向来验收。

主结果必须注明健康指挥零误拒绝、额外检查资源和单点风险等限定。记录command负荷与阻塞，不能只显示成功纠错。

### 7.3 信息等待与范围

fast/balanced/integrated在autonomy/full、三个时限下运行。登记balanced−fast、integrated−balanced、integrated−fast；在同信息政策下计算human−autonomy。信息等待最多到任务到期，因此时限不仅是评分标签。

主信息交互只采用autonomy；full下相同交互作为次级。读取覆盖率用于等待，而不是潜在clean比例。信息不足参数和补充检查强度均有关闭机制的消融/敏感性，不能把函数单调性误当成外部经验发现。

审核范围只比较all、external、direct_control，排除把没有外部权限的节点作为“外部审核对象”而制造重复。执行倾向切片只回答异常方案转为动作的条件概率依赖性。

### 7.4 截尾与评分敏感性

hard/grace、受损效用和权重敏感性均从同一轨迹重算。延长horizon则确实新增轨迹配置，必须与相同条件下较短窗口共享随机过程前缀。报告各窗口内human效应与未完成任务，不将不同长度累计损失直接作为政策优劣比较。

全部时间长度都是抽象单位。短期窗口不要求cap1把所有任务清空，也不把未完成样本从统计中删除。不能通过不断延长模拟直到某个政策排名稳定来挑窗口。

### 7.5 审核容量曲线与监督拥塞

本补充实验属于RQ3，保留原人工实验。固定A04初始错误、无资源冲击、full、all、life_safety、deadline_window=5、review_service_time=3；审核灵敏度/特异度、information policy及其他参数保持中心值，指挥为distributed。仅改变附录 `oversight_capacity` 的七档容量；`unlimited`沿用既有“消除容量排队、仍需完整服务时长”的语义。每档full均减去相同外生情景的autonomy，规范化后复用同一个参照，不给它复制七份随机样本。

运行前规定每档 **human−autonomy** 的L均值差、F1–F7差及最大单项功能缺口差；按容量顺序全部展示。报告审核请求与完成数、未开始服务的普通/生命安全加权排队tick、未完成任务、截止窗口内已观察到的deadline miss、五项互斥阻塞分解、误拒绝及外部错误动作的水平和差。完成数不包含恰在t=horizon才能完成的服务。排队积分和服务阻塞不同，不能相加充当独立因果贡献。

“**监督拥塞**”操作性地指：危机响应窗口内，需审核任务形成的监督需求超过可用人工处理能力，审核虽可能减少错误行动，却可能通过排队、未完成和延期产生新的公共功能损失。这是本文从模型提出的机制概念，尚非现实经验验证的普遍定律。结合全部容量的排队、完成、延期、错误动作和ΔL检查明显过载、过渡及边际收益减弱；相邻格点的水平变化仅作描述，不新增事后显著性检验。若置信区间支持从净损害到净收益，只报告离散容量间的区间，不插值构造临界容量；若无清晰阈值、无单调关系或没有反转，照实保留。生命安全优先是固定价值偏好，F1/F2等功能可能受挤压，不解释为普遍最优治理。

## 8. 配置规范化、去重与对比所有权

### 8.1 语义去重而非文件名去重

先展开family再规范化实际行为配置：

1. `shock_type=none`时资源概率、K、partition、展开方式等无消费者字段从身份中删除。
2. 有资源时将K/partition解析为精确成员组；身份用组集合，不把seed标签当成行为差异。组内和组间排序固定。
3. 无人工审核时删除人工质量、队列、范围、优先级字段；无指挥gate时删除指挥服务参数。
4. 无自动隔离且没有其他检测结果消费者时删除检测字段（包括monitoring_offset）；fixed-budget启用时删除无消费者的observation_level。monitoring_offset为空表示原持续监测，正整数表示一次release-relative检测；无额外核验时删除额外核验质量。
5. 映射、评分视图、RQ、family、输出路径、展示标题、role ID及agent/function纯显示name不进入物理config身份。
6. 保留所有真正影响动力学、观察窗口或已注册raw的参数；不可只因某个Pilot样本里没走到分支就删除字段。

身份由固定序列化对象的SHA-256决定；列表按科学集合语义排序，保留有序维度的顺序；数字统一格式，布尔不能与整数混同。same active configuration只能模拟一次，多个科学role可以引用它。

### 8.2 对比与结构性零

一个对比是有限项`(cell_id, coefficient)`的线性组合。先按cell合并系数、删除精确零系数、按ID排序。直接对比的有效系数一般为+1/−1；交互允许因共享参照抵消为两项。不能凭“项数”判断其科学解释。

完全抵消的对比保留为`structural_zero`，点估计和区间精确为0，不bootstrap；保留请求该对比的科学角色。其他对比不能因为观察样本恰好都为0就声称数学零效应。

相同规范化对比、metric、view、statistic只有一条统计结果，多个RQ/用途引用它。不得通过改purpose名字重复导出同一真值。不存在的参照、重复相反方向但未登记的对比、非有限系数必须失败。零系数和恒等参照不增加cell。

### 8.3 次级估计量的生成规则

以下是完整规则，不允许Formal后再加：

- dependency及其partition：§5.3全部相邻/基准K1对比；均值、ES95、曾受损数、外部错误动作；均值另含F1–F7及最大单项功能缺口。
- observation：§6.1全部隔离、暴露直接效果及两类固定端点交互。
- detection：§6.2组合参照与两轴相邻对比。
- fixed_budget：§6.4的三个时点对比；主视图均值和L的ES95及同尾部功能分解。
- verification：§6.3三种策略对比及A04相邻质量对比。
- human与审核OFAT：每个full cell对匹配autonomy；对OFAT另比较同条件中心full。
- oversight_capacity：§7.5每档full对匹配autonomy；全部诊断及非补偿性结果使用均值。
- triage：§7.1两个优先级对FIFO及容量交互。
- command及容量/质量：每组条件下selective/centralized对distributed、centralized对selective；在同一结构及其他参数相同下，全部登记capacity3−1，以及质量.4−0、.8−.4的相邻对比；所有无指挥参数差异规范化为相同参照。
- information：§7.3三个政策对比及同信息政策下human对照。
- review_scope：external−all、direct_control−all。
- execution：每个执行倾向下full−autonomy；不跨倾向直接解释监督效应。
- information_error与supplemental_check：每档参数内integrated−fast，及该差值对中心参数的差中差。
- horizon：同窗口内full−autonomy；其与中心窗口效应的差记“窗口依赖”，不当成现实政策效果。

除dependency与fixed_budget的ES95外，次级比较默认统计量为均值。最大单项功能缺口仅按主视图求均值，不把其ES95或其他视图展开。除主结果规定的评分敏感性外，不把每个次级对比再与全部view相乘。

## 9. 统计估计、共同随机数与不确定性

### 9.1 均值和尾部是不同统计量

对权重`a_j`和每项配置分布`Y_j`，均值对比为：

$$\hat\Delta_{mean}=\sum_j a_j\bar Y_j.$$

ES95对比是`sum_j a_j ES95(Y_j)`，**不是**`ES95(sum_j a_j Y_j)`。经验尾部按精确5%样本质量：损失降序排列，令`m=0.05N,k=floor(m),r=m-k`，计算`(前k项之和+r×下一项)/m`。这对Smoke的小N也有定义，不把随意取ceil个样本当成同一估计量。

**尾部功能分解**使用每个cell总损失L的同一尾部权重。设边界损失为z，严格大于z的样本权重为1；等于z的所有样本平均分配剩余尾部质量，使总权重恰为0.05N；其余为0。对每项功能计算`sum_r tail_weight_r × L_f,r /(0.05N)`，加权后恰好重建总ES95。对比再按同一已登记系数相加。边界并列不得按run ID优先挑选某个功能组合。表中标为`tail_component`，它不是该功能自身损失分布的ES95，也不表示处理与参照选中了同一批尾部run。Bootstrap每次重新选择总尾部并分解。

### 9.2 同一潜在场景与独立随机机制

随机根只由固定master seed和run index构造；具体键为具有类型的稳定元组：`(master_seed,run_index,mechanism,entity,event_time,event_ordinal)`。该元组必须编码为UTF-8 JSON数组（ensure_ascii=false、无多余空格；对象键排序、实体集合排序），SHA-256后取前52bit，令`U=(x+0.5)/2^52`，得到严格在(0,1)内的确定性伪随机数。禁止使用Python进程随机hash。

键**不含config hash、policy、treatment、family或输出路径**。资源组键采用资源类型与成员集合；消息采用发送者、接收者和发送tick（同tick最多一次）；审核判断采用节点任务身份与判断类别；持续检测/误报采用节点与tick，一次主动检查采用节点任务身份；回滚采用节点的首个错误动作身份。外生冲击、补充检查、信息不足、审核与回滚使用不同mechanism域。

全部潜在随机键按下表冻结；一个窗口每节点只有一个初始任务，因此以节点ID即可代表该任务。表外不得新增共享随机域：

| mechanism | entity | event_time |
|---|---|---|
| `resource_group` | `[资源类型, 排序后组成员]` | 0 |
| `exposure`、`data_local` | `[资源类型, 节点ID]` | 0 |
| `local`、`extra`、`adopt` | `[发送节点, 接收节点]` | 发送tick |
| `supplemental` | 接收节点ID | 检查tick |
| `missing` | 节点ID | 0 |
| `detect`、`false_alarm`（持续监测） | 节点ID | 监测tick |
| `detect_once`、`false_alarm_once`（fixed-budget） | 节点ID | 0 |
| `review_sensitivity`、`review_specificity` | 节点ID | 0 |
| `command_intercept`、`command_corrupt` | 目标节点ID | 0 |
| `unsafe_execute`、`rollback` | 节点ID | 0 |

所有`event_ordinal=0`，因为同一身份同tick至多一次对应抽样。改变任务次数或同tick重复服务属于科学语义改变，不偷偷递增序号。不同机制各用独立域；同一任务延迟完成时仍用同一潜在判断抽样，避免排队顺序本身重抽“运气”。

不同成员组没有一一对应时，不伪装成相同资源组；可以共享其他有明确含义的随机事件。同run index的多配置结果联合保存。CRN只用于减少无关模拟波动，**不保证对所有对比方差一定更小，也不建立现实世界的个体因果配对**。

### 9.3 Bootstrap

除位置的固定折簇bootstrap外，其他估计量统一按run index对全部term联合重抽样。每个重复中重新计算各cell均值或ES95，再执行规范化线性组合。不能独立重抽共享参照，也不能只bootstrap已算好的ES差值。

重抽样整数索引统一采用`Generator(PCG64(SeedSequence([bootstrap_master_seed, domain])))`：domain=0生成所有线性对比共享的B×N索引矩阵，domain=1和2分别生成位置两折的B×N_fold索引矩阵；使用整数`integers(0,N,size=...,dtype=int64)`，不在估计量循环中依次消费生成器。复算按完整矩阵同一行取索引；分块运行不能改变索引。软件版本由依赖锁定。

95%区间使用2.5%和97.5%分位数，线性插值约定固定为NumPy quantile的`method="linear"`。全部为pointwise百分位模拟区间，不承诺同时覆盖所有格点。数值恰好落在0边界按不确定处理，结构性零例外。

`ci_low>0`为positive，`ci_high<0`为negative；其余为uncertain。undefined单列原因，不转为0。结构性零必须由规范化或明确恒等合同证明，不能从一组相同样本推出。

### 9.4 蒙特卡洛误差与抽样规则

附录固定Pilot/Formal/Bootstrap/Smoke种子和数量，不做自适应采样。研究不确定性由预定bootstrap区间报告；位置估计保留有效bootstrap次数和未定义原因，不把参数不确定性混进MC区间。

不得看Formal结果追加样本。若存在非有限值、错误索引或估计量算法缺陷，必须修实现并重新Pilot；不能用“差一点显著”作调整理由。正式每cell统一样本量；本协议不授权临时精度自适应或更换随机种子。

## 10. Raw、三张统计表与图表的消费者

### 10.1 Raw

四个30维积分和`model.md` §8.4规定的标量构成run级raw；另记录run index与配置指纹，不另造重复总指标。按cell存一份可校验的数组及schema；不保存重复完整config副本或所有run的无限消息日志。诊断trace只用于预定夹具或少量预定演示run。

完整 run 级数组按配置 ID 保存到运行目录的 `raw/`，写入前验证 schema、边界和 run index。抽样由附录A规定，不保存每个 cell 的重复完整配置，不把旧归档数据用作当前实验结果。

四个积分分别有hard/grace和受损效用重算消费者；七项功能、加权总loss从它们派生。若实施者改变任何字段，必须同步解释消费者和公式，而不是给raw无限增加看似有用的统计量。

### 10.2 Published tables

- `effects.csv`：长表，包含cell级均值/ES95水平行，以及direct、interaction、structural_zero结果。level行是单cell统计量，不受零和系数限制；contrast行必须零和。
- `position.csv`：三个映射下位置交叉拟合结果和支持状态。
- `position_strata.csv`：全部被观察到的K×位置支持量与均值。

`effects.csv`必须有`estimand_id, estimand_type, statistic, view, metric, value, ci_low, ci_high, status, direction, n_runs`及记录配置或对比 ID 的 `catalog_id`。对没有计算区间的纯level诊断行，区间为空并注明`not_computed`，不得填0。功能分解作为不同metric行，不建7张新表；结构性零行保留。

### 10.3 十张有明确用途的图

| 图 | 固定消费者与选择规则 |
|---|---|
| 1 | 公共危机过程、3RQ和边界；讲义术语沿用，图由本研究自绘，不复制受限课件 |
| 2 | 配置生成的业务图，区分required/supplemental与指挥gate；标出真实存在的信息用途 |
| 3 | 主位置增量R²与§5.2的固定同规模示例；成员映射敏感性明确标次级 |
| 4 | data、p=.20、K2−K1、基准及四个预定partition的均值/ES95，不换切片 |
| 5 | 两种暴露方式×三个O的隔离效果，同时显示功能损失与阻塞/误隔离 |
| 6 | 主人工效应的时限/容量结果；指挥三结构在autonomy下的时限效果；叠加人工只作次级注释 |
| 7 | 两档有限容量×三个时限的三种分诊；总loss和七项功能分解，队列诊断不作第二个福利证明 |
| 8 | 信息政策×时限，显示已接受覆盖、真实正确比例及损失/阻塞；不能只保留最终行动者 |
| 9 | fixed-budget三项时点对比、F1–F7和实际检查次数；均值为主，ES95在报告中列为次级 |
| 10 | 全部七档容量的human−autonomy曲线、F1–F7及排队/完成诊断；unlimited为独立类别，不伪造连续容量 |

图中一条曲线连接离散条件，只为阅读，不估计连续临界点。CI跨0的格点直接显示不确定。所有筛选与排序规则由分析代码和实验设计确定，`figures.py`只渲染，不临时挑最大效应、显著个数或漂亮示例。图内标题不得预写“证明人工有害”等结果。

## 11. 实现验证与Pilot验收

### 11.1 验证证据的范围

文档解析、图集合、配置去重和对比存在性不代替动力学验证。以下行为由 `test_model.py` 和 `test_pipeline.py` 检查；Smoke、Pilot、Formal 负责实际研究计算。

### 11.2 必须覆盖的合同

**配置与研究边界**：基础块可解析；30个唯一节点、正权重、合法权限；边无重复；必要输入DAG；A29有正常输入/输出消费者；资源用户存在且K不超过人数；额外partition确定；所有family外生情景显式；精确值无旧配置隐式继承。

**信息与潜在真值**：被接受但错误的信息提高C_obs而不提高C_clean；政策不读潜在真伪；拒绝新消息不复用旧clean覆盖；缺失错误在审核前一次产生；消息核验计正常负荷；补充检查只有正确新信息产生成功机会，但允许失败；无补充信息时不除零；同tick输入顺序不改变结果；延迟至少1；回路事件有界。

**生命周期**：初始污染、方案、内部暂定发送、审核、指挥、执行顺序明确；审核完成读当前真值；服务s从start到start+s，不加隐形tick；false denial精确hold；隔离不抹除在审投入；A28不可用暂停指挥；异常方案执行只抽一次；审核漏检不强制错误执行；工具失败发生在正确阶段；无外部权限不计wrong_action。

**恢复与成本**：恢复不免疫；历史消息不能撤回；错误动作回滚失败不会被改健康状态抹去；每个错误动作至多一次回滚；五项阻塞互斥且和≤30T；review/command包括队列和在服；hold有消费者；队列加权诊断只计未在服；期末未完成与未恢复保持在结果中。

**数学与统计**：四积分能手算重建所有评分视图；主要函数bounds正确；ES95并列尾部功能贡献可重建总尾部；阈值时长不从积分伪算；R²负值不裁剪；全常数分母undefined；固定折按run簇；ES95差不等于差值的ES95；共享参照合并；四项交互与化简项相等；恒等对比精确为0；CRN不依赖调用顺序；无一一对应资源组不伪共享。

**实验与展示**：每个主term命中唯一配置；每条次级对比可生成；无消费者参数规范化；角色复用但不删除null；全部主量有固定消费者；主图切片不能按效果调整；长窗口前缀完全一致；所有finite指标有定义和单位。

**补充实验**：fixed-budget每Agent每run至多一次机会、目标为release+offset、超窗不补查、三组质量相同且随机数对齐、关闭隔离规范化、显示名不改变身份；capacity全部七档与匹配参照、unlimited保持服务时长、外生情景一致；审核请求=已完成+仍排队+仍在服（trace核验），raw完成数不大于请求数，误拒绝不大于完成数。最大功能缺口仅由已有积分派生；所有阶段共用执行、统计与图表路径。

### 11.3 不能作为验收标准的内容

不要求任何政策显著更好，不要求出现反转或均值/尾部权衡，不要求每条边在小样本都传播过，不要求due_first在每个情景都与FIFO不同，也不要求补充信息、领导或人工监督出现某种结论。

零传播测试应限定为“没有边采用引发的新污染”，不能因为信息不足或资源冲击还存在就判失败。无限容量只消除排队，不消除服务时长。零指挥纠错不保证总loss更高，因等待还能改变信息到达。健康且及时的理想服务轨迹才应总loss为0。

## 12. 复算与允许的修改

科学周期：验证 → Smoke → Pilot → 独立接受 → Formal → 最终统计/独立复算。Smoke 遍历全格点；Formal 按附录执行 Bootstrap、统计与固定图表。

本次补充实验的定义先于其Smoke/Pilot/Formal写入本文；运行目录保留开始时的协议/源码哈希、环境、种子、设计指纹和结束时的产物校验，失败保留部分输出。Pilot后以独立计算路径核对配置覆盖、请求/队列守恒、功能分解、统计和报告，不以方向验收；通过后才启动Formal。Formal另与修改前已有输出核对原有配置的全部共同raw字段，并独立复算关键数字。独立复算指不调用生产估计函数的核对，不宣称获得未经实施的外部专家或人工审定。历史实验的时间链不足以证明事前登记，因此全文称实验协议或预先规定的比较，不作整个历史研究已获事前登记证明的宣称。

仅涉及排版、参考文献格式或措辞且不改公式、参数、选择和估计的展示修改不重跑模拟。科学语义变化必须重新 Pilot、独立接受后才能进入 Formal。

已有源码和两份说明不一致时属于待修缺陷，不能把旧结果当成更高权威来反改假设。已运行过Formal之后，不允许用重新Pilot为按方向调参辩护。新科学设计可以改变问题，但必须明确另行审定，不能悄悄回填为原协议内的比较。

## 13. 给课程报告的使用约束

模型/协议的技术篇幅不计入约4000字政策分析报告正文。报告应把三个问题讲清楚，而非依次介绍所有family。依课程大纲，小组报告约4000字、展示7分钟；本协议不把个人作业的日期和小组研究报告日期混用。

论文可以报告某项预定合成情景中的差异、零结果、反向和不确定，也可以提出待实地验证的治理建议；不能宣称外部校准已经完成。保留“公共功能受损不自动等于公共危机”的边界。AI协助程度及小组核验责任应依课程要求如实说明。

## 附录A. 实验与评分的精确定义

本块是格点、种子和视图的唯一手工维护位置，数值均在查看本设计的新Formal结果之前固定。实验设计仅由 `study.build_catalog()` 展开。主效应统一使用主视图，并按§3.2重算预先规定评价敏感性，不设置逐项view选择字段。正文与该块如不一致，必须先修订，不能运行时自行挑选解释。

<!-- BEGIN EXPERIMENT SPEC -->
```yaml
sampling:
  pilot_runs: 500
  formal_runs: 5000
  bootstrap_repetitions: 1000
  smoke_runs: 8
  smoke_bootstrap: 20
  seeds:
    pilot: 2026100301
    formal: 2026100302
    bootstrap: 2026100303
    smoke: 2026100304
families:
  - {id: position, rq: RQ1, tier: primary, fixed: {shock_type: none, command_structure: distributed}, axes: {initial_nodes: [[A01], [A02], [A03], [A04], [A05], [A06], [A07], [A08], [A09], [A10], [A11], [A12], [A13], [A14], [A15], [A16], [A17], [A18], [A19], [A20], [A21], [A22], [A23], [A24], [A25], [A26], [A27], [A28], [A29], [A30]]}}
  - {id: dependency, rq: RQ1, tier: secondary, fixed: {initial_nodes: [], partition_seed: 0}, axes: {shock_type: [model, data, tool], shock_probability: [0.05, 0.1, 0.2, 0.4], resource_groups: [1, 2, 3, 5, 10]}}
  - {id: dependency_partition, rq: RQ1, tier: sensitivity, fixed: {initial_nodes: [], resource_groups: 2}, axes: {shock_type: [model, data, tool], shock_probability: [0.1, 0.2], partition_seed: [4101, 4102, 4103, 4104]}}
  - {id: observation, rq: RQ2, tier: primary, fixed: {initial_nodes: [], shock_type: data, shock_probability: 0.2, resource_groups: 1, partition_seed: 0, command_structure: distributed}, axes: {shock_profile: [abrupt, progressive], observation_level: [0, 1, 2], automatic_isolation: [false, true]}}
  - {id: detection, rq: RQ2, tier: secondary, fixed: {initial_nodes: [], shock_type: data, shock_probability: 0.2, resource_groups: 1, partition_seed: 0, command_structure: distributed, observation_level: 2, automatic_isolation: true}, axes: {shock_profile: [abrupt, progressive], detection_probability: [0.2, 0.5, 0.8], false_alarm_probability: [0.001, 0.005, 0.02]}}
  - {id: fixed_budget, rq: RQ2, tier: secondary, fixed: {initial_nodes: [], shock_type: data, shock_probability: 0.2, resource_groups: 1, partition_seed: 0, shock_profile: abrupt, command_structure: distributed, automatic_isolation: true}, axes: {monitoring_offset: [1, 3, 5]}}
  - {id: verification, rq: RQ2, tier: secondary, fixed: {shock_type: none, command_structure: distributed}, axes: {initial_nodes: [[A04], [A08], [A12], [A21], [A28]], verification_mode: [none, critical, global]}}
  - {id: verification_quality, rq: RQ2, tier: sensitivity, fixed: {initial_nodes: [A04], shock_type: none, command_structure: distributed}, axes: {verification_mode: [critical, global], verification_effectiveness: [0.2, 0.8]}}
  - {id: human, rq: RQ3, tier: primary, fixed: {initial_nodes: [A04], shock_type: none, command_structure: distributed}, axes: {oversight: [autonomy, full], deadline_window: [2, 5, 10], review_capacity: [1, 3, unlimited]}}
  - {id: oversight_capacity, rq: RQ3, tier: secondary, fixed: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: full, review_scope: all, review_priority: life_safety, deadline_window: 5, review_service_time: 3}, axes: {review_capacity: [1, 2, 3, 4, 6, 10, unlimited]}}
  - {id: review_sensitivity, rq: RQ3, tier: sensitivity, fixed: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: full}, axes: {review_sensitivity: [0.6, 0.95], deadline_window: [2, 5, 10]}}
  - {id: review_specificity, rq: RQ3, tier: sensitivity, fixed: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: full}, axes: {review_specificity: [0.9, 0.99], deadline_window: [2, 5, 10]}}
  - {id: review_duration, rq: RQ3, tier: sensitivity, fixed: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: full}, axes: {review_service_time: [1, 5], deadline_window: [2, 5, 10]}}
  - {id: triage, rq: RQ3, tier: primary, fixed: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: full}, axes: {review_priority: [fifo, due_first, life_safety], review_capacity: [1, 3], deadline_window: [2, 5, 10]}}
  - {id: command, rq: RQ3, tier: primary, fixed: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: autonomy}, axes: {command_structure: [distributed, selective, centralized], deadline_window: [2, 5, 10]}}
  - {id: command_with_human, rq: RQ3, tier: sensitivity, fixed: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: full, deadline_window: 5}, axes: {command_structure: [distributed, selective, centralized]}}
  - {id: command_capacity_quality, rq: RQ3, tier: sensitivity, fixed: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: autonomy, deadline_window: 5}, axes: {command_structure: [distributed, selective, centralized], command_capacity: [1, 3], command_intercept_effectiveness: [0.0, 0.4, 0.8]}}
  - {id: information, rq: RQ3, tier: primary, fixed: {initial_nodes: [A04], shock_type: none, command_structure: distributed}, axes: {information_policy: [fast, balanced, integrated], oversight: [autonomy, full], deadline_window: [2, 5, 10]}}
  - {id: review_scope, rq: RQ3, tier: sensitivity, fixed: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: full}, axes: {review_scope: [all, external, direct_control], deadline_window: [2, 5, 10]}}
  - {id: execution, rq: RQ3, tier: sensitivity, fixed: {initial_nodes: [A04], shock_type: none, command_structure: distributed, deadline_window: 5}, axes: {execution_autonomy: [0.4, 0.8, 1.0], oversight: [autonomy, full]}}
  - {id: information_error, rq: RQ3, tier: sensitivity, fixed: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: autonomy, deadline_window: 5}, axes: {information_error_rate: [0.0, 0.1, 0.25, 0.5], information_policy: [fast, integrated]}}
  - {id: supplemental_check, rq: RQ3, tier: sensitivity, fixed: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: autonomy, deadline_window: 5}, axes: {supplemental_check_effectiveness: [0.0, 0.25, 0.5], information_policy: [fast, integrated]}}
  - {id: horizon, rq: RQ3, tier: sensitivity, fixed: {initial_nodes: [A04], shock_type: none, command_structure: distributed, horizon: 32}, axes: {oversight: [autonomy, full], deadline_window: [2, 5, 10]}}
primary_effects:
  - {id: R1_dependency_mean, rq: RQ1, statistic: mean, terms: [{coefficient: 1, select: {initial_nodes: [], shock_type: data, shock_probability: 0.2, resource_groups: 2, partition_seed: 0, command_structure: distributed}}, {coefficient: -1, select: {initial_nodes: [], shock_type: data, shock_probability: 0.2, resource_groups: 1, partition_seed: 0, command_structure: distributed}}]}
  - {id: R1_dependency_ES95, rq: RQ1, statistic: ES95, terms: [{coefficient: 1, select: {initial_nodes: [], shock_type: data, shock_probability: 0.2, resource_groups: 2, partition_seed: 0, command_structure: distributed}}, {coefficient: -1, select: {initial_nodes: [], shock_type: data, shock_probability: 0.2, resource_groups: 1, partition_seed: 0, command_structure: distributed}}]}
  - {id: R2_observation_interaction, rq: RQ2, statistic: mean, terms: [{coefficient: 1, select: {initial_nodes: [], shock_type: data, shock_probability: 0.2, resource_groups: 1, partition_seed: 0, command_structure: distributed, shock_profile: abrupt, observation_level: 2, automatic_isolation: true}}, {coefficient: -1, select: {initial_nodes: [], shock_type: data, shock_probability: 0.2, resource_groups: 1, partition_seed: 0, command_structure: distributed, shock_profile: abrupt, observation_level: 2, automatic_isolation: false}}, {coefficient: -1, select: {initial_nodes: [], shock_type: data, shock_probability: 0.2, resource_groups: 1, partition_seed: 0, command_structure: distributed, shock_profile: abrupt, observation_level: 0, automatic_isolation: true}}, {coefficient: 1, select: {initial_nodes: [], shock_type: data, shock_probability: 0.2, resource_groups: 1, partition_seed: 0, command_structure: distributed, shock_profile: abrupt, observation_level: 0, automatic_isolation: false}}]}
  - {id: R2_profile_interaction, rq: RQ2, statistic: mean, terms: [{coefficient: 1, select: {initial_nodes: [], shock_type: data, shock_probability: 0.2, resource_groups: 1, partition_seed: 0, command_structure: distributed, shock_profile: progressive, observation_level: 2, automatic_isolation: true}}, {coefficient: -1, select: {initial_nodes: [], shock_type: data, shock_probability: 0.2, resource_groups: 1, partition_seed: 0, command_structure: distributed, shock_profile: progressive, observation_level: 2, automatic_isolation: false}}, {coefficient: -1, select: {initial_nodes: [], shock_type: data, shock_probability: 0.2, resource_groups: 1, partition_seed: 0, command_structure: distributed, shock_profile: abrupt, observation_level: 2, automatic_isolation: true}}, {coefficient: 1, select: {initial_nodes: [], shock_type: data, shock_probability: 0.2, resource_groups: 1, partition_seed: 0, command_structure: distributed, shock_profile: abrupt, observation_level: 2, automatic_isolation: false}}]}
  - {id: R3_human_deadline, rq: RQ3, statistic: mean, terms: [{coefficient: 1, select: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: full, deadline_window: 2}}, {coefficient: -1, select: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: autonomy, deadline_window: 2}}, {coefficient: -1, select: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: full, deadline_window: 10}}, {coefficient: 1, select: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: autonomy, deadline_window: 10}}]}
  - {id: R3_human_capacity, rq: RQ3, statistic: mean, terms: [{coefficient: 1, select: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: full, deadline_window: 5, review_capacity: 1}}, {coefficient: -1, select: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: autonomy, deadline_window: 5}}, {coefficient: -1, select: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: full, deadline_window: 5, review_capacity: 3}}, {coefficient: 1, select: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: autonomy, deadline_window: 5}}]}
  - {id: R3_life_vs_fifo, rq: RQ3, statistic: mean, terms: [{coefficient: 1, select: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: full, deadline_window: 5, review_capacity: 1, review_priority: life_safety}}, {coefficient: -1, select: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: full, deadline_window: 5, review_capacity: 1, review_priority: fifo}}]}
  - {id: R3_command_deadline, rq: RQ3, statistic: mean, terms: [{coefficient: 1, select: {initial_nodes: [A04], shock_type: none, command_structure: centralized, oversight: autonomy, deadline_window: 2}}, {coefficient: -1, select: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: autonomy, deadline_window: 2}}, {coefficient: -1, select: {initial_nodes: [A04], shock_type: none, command_structure: centralized, oversight: autonomy, deadline_window: 10}}, {coefficient: 1, select: {initial_nodes: [A04], shock_type: none, command_structure: distributed, oversight: autonomy, deadline_window: 10}}]}
  - {id: R3_information_deadline, rq: RQ3, statistic: mean, terms: [{coefficient: 1, select: {initial_nodes: [A04], shock_type: none, command_structure: distributed, information_policy: integrated, deadline_window: 2, oversight: autonomy}}, {coefficient: -1, select: {initial_nodes: [A04], shock_type: none, command_structure: distributed, information_policy: fast, deadline_window: 2, oversight: autonomy}}, {coefficient: -1, select: {initial_nodes: [A04], shock_type: none, command_structure: distributed, information_policy: integrated, deadline_window: 10, oversight: autonomy}}, {coefficient: 1, select: {initial_nodes: [A04], shock_type: none, command_structure: distributed, information_policy: fast, deadline_window: 10, oversight: autonomy}}]}
evaluation_views:
  primary: {members: configured, function_criticality: configured, timeliness: hard, compromised_utility: base}
  equal_member: {members: equal, function_criticality: configured, timeliness: hard, compromised_utility: base}
  agent_criticality: {members: agent_criticality, function_criticality: configured, timeliness: hard, compromised_utility: base}
  equal_function: {members: configured, function_criticality: equal, timeliness: hard, compromised_utility: base}
  grace: {members: configured, function_criticality: configured, timeliness: linear_grace, compromised_utility: base}
  low_compromised_utility: {members: configured, function_criticality: configured, timeliness: hard, compromised_utility: 0.25}
  high_compromised_utility: {members: configured, function_criticality: configured, timeliness: hard, compromised_utility: 0.75}
```
<!-- END EXPERIMENT SPEC -->
