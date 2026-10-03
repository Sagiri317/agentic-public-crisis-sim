# 公共危机 Agent 合成情景研究

本项目围绕局部自主失效、信息与监测处置、时间压力下的复核和分诊开展三个研究问题的机制计算。七项公共功能的连续服务缺口是主结果；全部参数均为合成设定，尚无现实经验校准。

监测研究同时保留O0/O1/O2持续监测政策与每节点一次检查的等预算时点实验；审核容量曲线用于研究监督需求、排队和延期形成的“监督拥塞”。七功能向量和最大单项功能缺口揭示总量可能掩盖的取舍。仓库仍是synthetic mechanism study，不是现实预测模型，也不是郑州真实组织结构复刻。

[模型语义](docs/model.md)、[实验协议](docs/experiment_protocol.md)、[精确基础配置](configs/base.yaml)分别规定科学规则、实验设计和基础数值。每次运行从协议和基础配置生成一次内存中的实验设计；评价敏感性从同一原始轨迹派生。

使用 Python 3.12 的 `crisis-sim312` Conda 环境。已安装依赖的精确版本见 `reproducibility/requirements-lock.txt`。无需大模型服务、密钥、交互式笔记本或外部数据。渲染需要系统中已有的中文字体。

```text
conda run -n crisis-sim312 python -m pytest -q
conda run -n crisis-sim312 python reproducibility/run_all.py --smoke
conda run -n crisis-sim312 python reproducibility/run_all.py --pilot --output .run/pilot --workers 8
conda run -n crisis-sim312 python reproducibility/run_all.py --formal --output .run/formal --workers 8
```

开发修改后，提交前运行 pytest 和 Smoke。pytest 验证科学合同；Smoke 遍历全部去重配置；Pilot 和 Formal 按协议固定抽样，复用同一执行、统计与展示路径。报告按 H/RQ 顺序显示主视图与评价敏感性。

科学流程为：验证 → Smoke → Pilot → 独立接受 → Formal → 最终统计/独立复算。科学语义变化还必须重新 Pilot，独立接受后才运行 Formal。

输出必须是不存在或为空的 `.run/<name>`；入口在计算前检查并拒绝覆盖。运行目录包含 `raw/`、`tables/` 中的三张 CSV、`figures/` 中的十张 PNG、`report.md` 和 `run-info.json`。后者保存运行前源码/协议哈希、环境、种子、设计指纹及完成后的产物哈希；只有整个流水线完成且源码未变化才标记complete。失败直接抛出异常并保留部分输出；重复运行请使用新的 `--output`。

代码 MIT；文档、报告和图 CC BY 4.0。引用信息见 [CITATION.cff](CITATION.cff)。
