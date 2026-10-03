# 研究约定

所有数值均为合成情景假设，不是现实公共危机概率或政策效力的估计。禁止为支持假设而调参。

开发前阅读 `docs/model.md` 和 `docs/experiment_protocol.md`。科学流程为：验证 → Smoke → Pilot → 独立接受 → Formal → 最终统计/独立复算。科学语义变化还必须重新 Pilot，独立接受后才运行 Formal；仅涉及展示的修改不触发科学重跑。保留失败运行的部分输出。

使用 `crisis-sim312` Conda 环境。开发修改后，提交前运行 `python -m pytest -q` 和 `python reproducibility/run_all.py --smoke`。复现不需要大模型服务、密钥、交互式笔记本或外部数据。

代码采用 MIT 许可证；文档、报告和图采用 CC BY 4.0。不得发布个人路径或认证信息。
