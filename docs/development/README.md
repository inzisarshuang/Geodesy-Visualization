# Development Baseline / 开发基线

This directory contains stable code-maintenance rules. Project-specific plotting parameters and result interpretation belong in the root README and the two example cfg files.

这里保存面向代码维护的稳定规则。具体研究区的绘图参数和结果解释由仓库根 README 与两个示例 cfg 维护。

## Reading Guide / 阅读指南

| Change type | Required reading |
|---|---|
| All code changes | `engineering_rules.md` |
| Python, PyGMT, or cfg interfaces | `python_rules.md` |
| Units, nodata, coordinates, or display ranges | `scientific_conventions.md` |
| `lib/pygmt_geo.py` changes or migration | `pygmt_geo_ownership.md` |
| AI coding-agent entry point | Repository-root `AGENTS.md` |

| 修改类型 | 必读文件 |
|---|---|
| 所有代码修改 | `engineering_rules.md` |
| Python、PyGMT 或配置接口 | `python_rules.md` |
| 单位、nodata、坐标或显示范围 | `scientific_conventions.md` |
| `lib/pygmt_geo.py` 修改或迁移 | `pygmt_geo_ownership.md` |
| AI 代码代理入口 | 仓库根目录 `AGENTS.md` |

The repository currently has no Shell workflow, so it does not include an empty `shell_rules.md`. Add that document only when an actual Shell entry point is introduced and maintained.

仓库目前没有 Shell 工作流，因此不设置空的 `shell_rules.md`。以后只有在新增并维护实际 Shell 入口时才补充，避免规范文件无效膨胀。

## What Belongs Here / 本目录内容

- Stable rules shared by multiple modules and future additions.
- Controls for scientific-meaning changes, excessive memory use, or incomplete products.
- Requirements verifiable through tests, static checks, or explicit visual inspection.

- 多个模块和后续新增代码都应遵守的稳定规则。
- 防止科学含义变化、内存过高或结果不完整的风险控制。
- 可以通过测试、静态检查或明确人工检查验证的要求。

Project-specific absolute paths, one-off experimental parameters, regional result interpretation, and temporary performance numbers do not belong here.

单个项目的绝对路径、一次实验的参数、区域结果解释和临时性能数字不放在这里。
