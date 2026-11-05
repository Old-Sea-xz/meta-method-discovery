# Meta Method Discovery

**不知道怎么入手，先找到合适的方法。**

面向 Agent 的专业方法发现 Skill：从普通语言描述识别方法缺口，检索成熟方法、核查来源与适用条件，并推进可执行的小试验。实际使用后，经用户确认保存经验，未来先检查条件再复用。


在用户缺少求解路径时，帮助 Agent 发现成熟的专业方法，核验来源与适用前提，并推进实际任务。保持通用检索流程，不维护封闭方法库，不依赖指定模型或搜索服务。

## 安装与使用

将整个 `meta-method-discovery` 文件夹复制到宿主的技能目录。Codex 默认位置为 `~/.codex/skills/meta-method-discovery`，Windows 通常为 `%USERPROFILE%\.codex\skills\meta-method-discovery`；设置了 CODEX_HOME 时使用该目录下的 `skills`。其他宿主按其 Agent Skills 加载机制安装。自动触发是否生效由宿主的技能发现能力决定。

重新加载技能或启动新会话。可以显式调用 `$meta-method-discovery 帮我找到适合解决这个问题的专业方法：……`；也可以直接描述复杂任务、目前的困境和限制，由 Agent 按 description 判断。纯翻译、事实问答、简单操作及指定方法的直接执行不触发。

方法发现只需 Markdown 与宿主已有的搜索/阅读能力。个人经验接口另需 Python 3.10+、PyYAML 和持久文件读写权限，不创建数据库或调用 Embedding 服务。没有搜索时必须标注未核验；没有持久权限时明确报告未保存。

## 个人经验知识库

每条经验独立存成带 YAML frontmatter 的 Markdown，默认位于 `~/.local/share/domain-method-finder/memory`，与 Skill 安装目录分离。可用 `DOMAIN_METHOD_MEMORY_HOME` 或 CLI `--root` 指定持久目录。用户实际反馈后先预览，再确认保存；拒绝后不催促，不自动保存草稿。

支持新增、关键词与结构标签查找、读取、更新、精确去重、删除和导出；保留失败、部分成功与历史版本。文件召回后由 Agent 语义判断适用条件，仍比较外部新方法。近似重复由 Agent 展示合并方案并获确认，不自动覆盖不同场景的记录。

数据结构、CLI 参数、授权边界及 API 示例见 [个人经验接口](references/personal-memory.md)。宿主负责可信身份、真实授权和串行写入；文件明文存储，路径隔离不等于操作系统权限隔离。此更新不会创建任何真实个人经验。

## 文件与验证

- `SKILL.md`：触发边界、核心流程和输出要求。
- `references/`：分类、检索、验证和过程示例，按需加载。
- `tests/`：开发测试资产和评测协议，禁止作为运行时上下文。

开发验证需要 Python 3.10+ 和 PyYAML（只用于解析 YAML，不是 Skill 运行依赖）：

```sh
python -m pip install pyyaml
python tests/validate.py
python -m unittest discover -s tests/ -p "test_*.py" -v
```

从交付包父目录运行上述命令。脚本检查真实 YAML、相对链接、样例结构、覆盖范围和重复提示；它不衡量 Agent 的触发准确率或方法发现质量。行为测试与 A/B 测试见 `tests/test_protocol.md`。

采用 [Agent Skills 官方规范](https://agentskills.io/specification)，2026-11-05 核对。安装不需要 OpenAI 专有配置文件；未设置工具白名单，以便兼容不同宿主。

## 第二轮增量修订

入口区分明确/可能/无方法缺口，约束未知时条件化推荐。有限搜索优先核对主推荐；正文数字和确定性不得超出实际证据。按需执行 references/method-trial.md 的低成本试验，未执行保持 UNVERIFIED。

个人经验继续使用 Markdown + YAML 与现有 Python/PyYAML 接口。语义适用性由宿主判断，关键词召回不能证明适用。多轮反馈、失败反例和条件归纳见 personal-memory.md；候选规律不自动写入。运行文件路径相对 SKILL 目录。新增行为用例须实际运行并独立评审，JSONL 解析通过不等于模型行为通过。

## 克隆安装

```sh
git clone https://github.com/Old-Sea-xz/meta-method-discovery.git
```

将仓库目录放入宿主技能目录，或使用宿主的 GitHub Skill 安装能力。入口为根目录 SKILL.md；显式调用名为 `$meta-method-discovery`。

## 兼容与效果边界

本项目由 Domain Method Finder 更名。为兼容已有经验，默认存储目录仍为 `~/.local/share/domain-method-finder/memory`，配置变量仍为 `DOMAIN_METHOD_MEMORY_HOME`；也可用 `--root` 指定新目录。更名不会自动迁移、删除或保存个人经验。

开发检查与存储回归不代表所有模型均能正确执行。8题定向外测由 DeepSeek 执行器自评报告通过，尚非独立全面评测。合成演示见 [记忆案例](docs/memory-showcase.md)，包括成功、失败与部分成功；不冒充真实用户研究。

## 复现合成记忆演示

```sh
python -X utf8 examples/run_memory_demos.py
```

依赖 Python 3.10+ 与 PyYAML，安装：`python -m pip install -r scripts/requirements.txt`。结果写入仓库 `demo-output/`，实际活动知识库使用临时目录，不访问真实个人库。
