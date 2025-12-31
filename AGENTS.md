# Repository Guidelines

## 项目结构与模块组织
- 业务代码位于 `src/quant/`，核心模块包括 `main.py`（入口）、`strategy.py`、`backtester.py`、`data_fetcher.py`。
- 配置在 `config/`（如 `config/config.py`），消息推送配置为 `config/notification_config.json`。
- 数据与产物分离：自选股与计划在 `data/`，图表输出在 `outputs/`。
- 说明文档集中在 `docs/`；虚拟环境目录为 `venv/`。

## 构建、测试与开发命令
- 创建/激活环境：`python -m venv venv` 然后 `source venv/bin/activate`。
- 安装依赖：`pip install -r requirements.txt`。
- 生成交易计划：`PYTHONPATH=src python -m quant.main`（可用 `--custom` 或 `--limit` 控制范围）。
- 运行回测：`PYTHONPATH=src python -m quant.backtester`。
- 生成可视化报告：使用 `quant.visualizer` 的辅助函数（示例见 `README.md`）。

## 编码风格与命名规范
- Python，4 空格缩进，UTF-8 编码。
- 函数/变量使用 `snake_case`，类使用 `CapWords`。
- 配置常量集中在 `config/config.py`（UPPER_SNAKE_CASE）。
- 模块保持单一职责；新增 CLI 入口时同步更新 `README.md`。

## 测试指南
- 当前没有正式测试套件。新增测试时使用 `pytest`，放在 `tests/` 下并命名为 `test_*.py`。
- 修改策略逻辑或数据获取时，至少添加一个最小化的冒烟测试。

## 提交与 PR 规范
- 提交信息遵循 Conventional Commits（如 `feat: add drawdown control`、`fix: handle empty data`）。
- PR 需要包含：简要摘要、变更原因、影响到的数据/图表产物说明。
- 若策略或参数有变化，更新 `README.md` 并注明配置差异。

## 安全与配置提示
- 不要在 `config/notification_config.json` 中提交密钥；Webhook token 请私下保存。
- 生成的 CSV/PNG 视为输出产物，除非明确需要，否则避免提交体积大或临时文件。
