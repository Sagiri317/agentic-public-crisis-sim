# 公共危机 Agent 合成情景研究

作者：邬丰骏、张云泽、贾子若、王志雄。

本项目服务于遵守学术规范的公共危机管理机制仿真论文 / 研究报告，围绕局部自主失效、信息与监测处置、时间压力下的复核和分诊开展三个研究问题的机制计算。七项公共功能的连续服务缺口是主结果；全部参数均为合成设定，尚无现实经验校准。

监测研究同时保留O0/O1/O2持续监测政策与检测次数受控的 release-relative 单次监测：early=release+1、middle=release+3、late=release+5，每节点最多一次。审核容量曲线研究监督任务超过及时处理能力后，经排队、延期和错失时限形成的额外公共功能损失；最终完成审核不等于及时完成。七功能向量和非补偿性跨功能稳健性指标揭示总量可能掩盖的取舍。仓库仍是synthetic mechanism study，不是现实预测模型，也不是郑州真实组织结构复刻。

[模型语义](docs/model.md)、[实验协议](docs/experiment_protocol.md)、[精确基础配置](configs/base.yaml)分别规定科学规则、实验设计和基础数值。每次运行从协议和基础配置生成一次内存中的实验设计；评价敏感性从同一原始轨迹派生。

使用 Python 3.12 的 `crisis-sim312` Conda 环境。已安装依赖的精确版本见 `reproducibility/requirements-lock.txt`。无需大模型服务、密钥、交互式笔记本或外部数据。渲染需要系统中已有的中文字体。

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
$env:NUMEXPR_NUM_THREADS = '1'
conda run -n crisis-sim312 python -m pytest -q
conda run -n crisis-sim312 python reproducibility/run_all.py --smoke
conda run -n crisis-sim312 python reproducibility/run_all.py --pilot --output .run/pilot --workers 8
conda run -n crisis-sim312 python reproducibility/run_all.py --formal --output .run/formal --workers 8
```

开发修改后，提交前运行 pytest 和 Smoke。pytest 验证科学合同；Smoke 遍历全部去重配置；Pilot 和 Formal 按协议固定抽样，复用同一执行、统计与展示路径。报告按 H/RQ 顺序显示主视图与评价敏感性。

科学流程为：验证 → Smoke → Pilot → 独立接受 → Formal → 最终统计/独立复算。科学语义变化还必须重新 Pilot，独立接受后才运行 Formal。只涉及展示、文档、运行信息或CI环境的修改不重跑Formal，可复用已有CSV核对图表与报告。

输出必须是不存在或为空的 `.run/<name>`；入口在计算前检查并拒绝覆盖。运行目录包含 `raw/`、`tables/` 中的三张 CSV、`figures/` 中的十张 PNG、`report.md` 和 `run-info.json`。后者仅保存stage、status、配置数、每配置抽样数、主种子、bootstrap数量与种子、Python和关键依赖版本、数值线程设置；整个流水线完成后标记complete。失败直接抛出异常并保留部分输出；重复运行请使用新的 `--output`。

代码 MIT；文档、报告和图 CC BY 4.0。引用信息见 [CITATION.cff](CITATION.cff)。
