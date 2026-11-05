# 测试协议

## 个人经验模块

执行 `python -m unittest discover -s tests/ -p "test_*.py" -v`。使用临时目录验证无授权不落盘、确认保存、新进程读取、相似/不相似检索、失败与部分成功可见、条件提示、版本更新、去重、删除、用户隔离、AI 推测拒绝、内容绑定与文件写入失败。不会生成真实个人经验。

这些测试验证接口约束，不能证明宿主永远正确获取确认、LLM 永远正确判断语义相似或历史失败必然改变其推荐。进一步用独立会话实测：拒绝保存后不再询问；同词异义不复用；不同约束解释排除原因；相似条件下对照成功与失败经验；保存后重启宿主再次推荐。测试中的标准经验不得进入运行时。

## 1. 静态检查

运行 `python tests/validate.py`。检查元数据、资源链接、JSONL、唯一 ID、正负样例数量和领域覆盖。通过仅代表文件与测试资产可用，不代表方法选择正确。

## 2. 触发测试

给被测 Agent 提供宿主正常的技能元数据与一条 prompt，不提供 expected_activate 或 rationale。每题使用新上下文，记录是否选择本 Skill，再由评测器比较标签。报告 precision、recall、accuracy、负样本 FPR 和混淆矩阵；不能把“按关键词分类”的脚本当作 Agent 行为验证。

## 3. 发现测试

仅提供 prompt，评测器保留其余字段。按 correctness、applicability、evidence、actionability、abstention 六项人工审阅，其中 correctness 包含问题抽象及专业方法发现。核查每条来源是否真实、是否实际支持论断；URL 存在不等于证据成立。候选方法接受开放答案，不以名称匹配评分。

网络禁用时验证未核验标注；缺数据时验证条件建议和拒绝伪精确；硬约束冲突时验证排除；已有明确方法时验证不无故重启探索。测试要求中的“不得”属于评测断言，不注入被测 Agent。

## 4. MetaMethodBench 配对实验

用户提供的 v0.1 原包放在工作区 `evaluation/`，不进入安装包。公开题已在开发过程中查看，不能再将其报告为未见盲测；私有标签不加载到技能作者或被测 Agent 上下文。预留一份未见扩展集再作独立泛化测试。

原基准的 `BENCHMARK.md`、`judge_prompt.md` 和评分脚本只供评测器审阅。被测 Agent 只接收单条 public prompt 和统一的输出记录要求，不接收原基准全文（它含方法示例）或私有标签。技能目录与运行时挂载白名单排除 tests、evaluation 和原 ZIP。

同一模型版本、工具权限、时间窗、token/搜索预算下，B0 禁用本 Skill，B1 启用本 Skill；按原基准建议各题重复 3 次，随机顺序、独立会话、记录真实答案、工具轨迹、来源快照、用时与调用成本。36 题 × 2 组 × 3 次为 216 次实际运行，不能由作者代写“预计答案”替代。

评测适配器按基准 schema 记录 task_id、activate_skill、problem_abstraction、status、methods、recommended_plan、missing_information、confidence；status 为 recommended / insufficient_information / no_reliable_method / not_applicable。方法的适用性等级与任务 status 分属不同层次，不要混用。JSON 是评测记录格式，不约束普通用户输出。

独立评审仅在作答完成后获得答案与对应私有标签，并按六维锚点评分；至少 20% 双审，真实检查来源。汇总触发、发现、适用性、来源、执行性、克制能力和严重错误，以及 Skill Lift 和成本。未完成 B0/B1 实测前不声称达到基准阈值。

原 `score.py` 仅覆盖部分汇总指标，而且默认缺失维度可不计权、缺失行为标记视为正确，也不拒绝重复 ID；使用前由评测器检查 ID 完整且唯一、各维分数范围、必要布尔字段、仅 C_transfer 有迁移分、两组样本严格配对，并独立报告激活正确性。不要将其输出当作全部验收指标。


## 5. E2 开发行为用例

以下 JSONL 是开发和后续行为评测资产，不是模型运行结果。文件位置相对 Skill 源目录：`tests/trigger_cases.jsonl`、`tests/discovery_cases.jsonl`、`tests/reuse_cases.jsonl`。保留原有字段和条目；新增字段为补充评测元数据，读取器应忽略未知字段。每行是独立 UTF-8 JSON 对象。

- `trigger_cases.jsonl`：原有用例后追加 12 条入口边界；`expected_state` 标注 METHOD_GAP / POSSIBLE_METHOD_GAP / NO_METHOD_GAP，`expected_activate` 仅表示是否应进入方法发现/澄清流程。它不是宿主实际加载事实。
- `discovery_cases.jsonl`：追加 6 对（12 条）条件变体，`pair_id` 标识共享目标的配对、`variant` 标识 A/B；另追加 6 条证据/试验场景。`acceptance` 和 `critical_errors` 供独立评审，不应提供给被测 Agent。
- `reuse_cases.jsonl`：12 组多轮经验场景。`turns` 为场景输入摘要，`fixtures` 规定仅用合成记忆夹具及隔离临时目录，`observable_expected`、`forbidden`、`decision_basis` 分别定义可观察预期、禁止行为和判定依据。执行者需将摘要扩为逐轮脚本并保存每轮原始答复及临时目录前后状态。

### 执行与判定

机械检查可验证 JSONL 逐行解析、ID 唯一、总量及 pair_id 每组恰有 A/B 两条；复用场景应为 12 组。触发标签可用于人工标注后的混淆矩阵。语义预期由不知道分组标签的独立评审依据每例 acceptance/forbidden 判定，并保留理由；文件校验或关键词命中不等于行为通过。

执行行为测试时每个触发/发现用例使用新上下文；每组复用场景从清洁隔离临时目录开始，按轮次记录输入、夹具状态、原始输出、工具轨迹和结果。确认、拒绝、跨身份、删除等状态须检查文件系统前后差异。只有确实执行的试验才记录观测结果；不可执行的试验标记未执行。该测试包本身不表示任何 LLM 行为测试已经运行或通过。

复用场景 turns 为逐轮 user/expected/new_session 对象；fixtures.records 为可验证记录及宿主别名映射。执行器在独立临时目录预装获批合成历史，将别名替换为真实 UUID，不能把夹具预装当作当前用户授权。
