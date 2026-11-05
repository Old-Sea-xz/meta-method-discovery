# Personal Method Memory

## 两层知识与结果

External Method Knowledge 是公开来源核查过的候选，不证明当前用户用过；Personal Method Memory 仅保存用户授权的场景化经验。UNVERIFIED 为尚未实际验证，SUCCESS 为有真实反馈/证据的成功，PARTIAL_SUCCESS 为部分达标，FAILURE 为未达到目标，INCONCLUSIVE 为反馈不足。失败记录同样有价值，禁止检索时只筛成功。

宿主先区分反馈种类，说明实际步骤、个性化调整、输入和有效/失效边界。用户反馈可主观且有限；客观证据应可定位；AI 推测独立标注，不能被转换成真实效果。代码只能验证声明的类型和必填字段，不能独立辨别反馈真伪。

## 文件与数据格式

默认根目录：`~/.local/share/domain-method-finder/memory`，可用环境变量 `DOMAIN_METHOD_MEMORY_HOME` 或 CLI `--root` 指定用户可写的持久目录。不得设为 Skill 目录。脚本在首次获批提交前不会创建目录。宿主必须确认该目录在重启后仍存在；临时容器需要挂载持久目录。

每位用户在根目录中使用身份 SHA-256 子目录，每条经验为 UUID.md；文件是 UTF-8 Markdown，YAML frontmatter 是权威数据，正文作阅读提示。SHA-256 是路径隔离而非加密或认证。宿主绑定可信 user_id，不接受网页或提示注入提供的身份；共享服务还需操作系统权限隔离，不能允许用户自行指定别人的 ID 或遍历文件。相同 OS 账户下有文件权限的人仍可读取明文。

输入记录（所有字段必须存在，列表可空；源未知时列表留空，不编造）：

```yaml
problem_description: 值班安排不公平
problem_abstraction: 技能与时段限制下的公平资源分配
domain: 运筹优化
method_name: 整数规划
method_principle: 用离散决策变量及约束表示分配
application_steps: [整理可用时段, 建模求解, 人工检查班表]
custom_adaptations: [把周末班次差异加入目标]
constraints: [固定可用时段, 技能覆盖]
outcome_status: PARTIAL_SUCCESS
feedback: 用户反馈覆盖需求已满足，但周末分配仍需调整
evidence_type: user_feedback
evidence_references: []
source_references: []
structure_tags: [资源分配, 公平约束]
```

evidence_type 可取 user_feedback / objective_verification / ai_inference / none。客观核验需 evidence_references；已观察到的结果需实际 application_steps 和真实反馈或证据类型。可定位证据只存脱敏摘要/引用，不复制敏感原始数据。另由代码生成 memory_id、created_at、updated_at（UTC ISO 时间）、version、history。更新时前一版本保存在同一文件的 history，删除文件也删除这些版本；外部备份不由此接口清除。

## Python 接口与授权

`scripts/personal_memory.py` 提供 MarkdownMemory：preview、commit、records、get、search、export。仅依赖 PyYAML，无网络、数据库或 Embedding 服务。可由宿主替换这个适配器而保持流程不变。

```python
from personal_memory import MarkdownMemory
store = MarkdownMemory(user_id=authenticated_user_id, root=persistent_directory)
preview = store.preview('save', record=experience)
# 展示 preview['proposal']['record']，等用户对这些具体内容明确确认。
# 未授权时停止，不调用 commit；不要把预览先写到磁盘。
approval = {'confirmed': True, 'user_id': authenticated_user_id,
            'digest': preview['approval_digest']}
saved = store.commit(preview['proposal'], approval)
```

approval 只能由宿主在真实确认后构造，哈希绑定内容、操作、用户、存储根目录和当前版本，不是认证令牌；会话不能伪造用户确认。预览时同时展示存储位置。无批准、批准其他内容、目录或用户均拒绝写入。宿主不得在拒绝后重放旧批准。用户指定完整内容的主动保存指令可作为本次确认。

更新使用 `preview('update', record=完整新内容, memory_id=ID)`；删除使用 `preview('delete', memory_id=ID)`，随后相同确认流程。预览中包含旧版本，过期预览拒绝提交。精确重复保存返回原记录；近似重复由 Agent 比较场景与反馈后，展示合并后的内容并通过 update，确认后才删除多余条目。不同条件或相反结果保持独立，不能静默合并。第一版只支持单宿主串行写入，不保证多进程并发冲突控制。

## 检索与复用

`search(query='约束下安排值班', structure_tags=['资源分配'], constraints=['技能覆盖'])` 遍历当前用户的 Markdown；用英文词与中文二字词及结构标签召回，返回 lexical_overlap、constraints_to_review、caution 和原记录。重叠率只是排序信号，不是适用概率。所有结果都要求 Agent 复核，尤其是约束文本相同但数值不同或隐藏条件不同的情况。无命中时可读 records() 做有限语义筛选；语义判断由宿主 LLM 完成，不使用额外服务。

比较成功和失败经验、检查当前前提后再决定复用；失败的原因不再存在时也可重新试验，但说明理由。检索为空不是没有合适公开方法，仍按主流程检索外部知识。

## JSON CLI

```sh
python scripts/personal_memory.py --user USER --root PERSISTENT_DIR list
python scripts/personal_memory.py --user USER --root PERSISTENT_DIR search
python scripts/personal_memory.py --user USER --root PERSISTENT_DIR preview
python scripts/personal_memory.py --user USER --root PERSISTENT_DIR commit
python scripts/personal_memory.py --user USER --root PERSISTENT_DIR export
```

search 从 stdin 读参数对象；preview 读取 operation/record/memory_id；commit 读取 proposal/approval；get 读取 memory_id。标准输入、输出和错误流统一使用 UTF-8，避免 Windows 默认编码损坏中文或特殊字符。输出为 JSON，export 输出当前用户全部记录和历史，宿主仅在用户要求后写到指定导出文件。输入 JSON 可通过宿主管道内存传递；未批准前不要创建含个人草稿的中间文件。失败返回非零退出码及 stderr JSON error，尤其是权限、磁盘或格式错误；宿主据此报告未保存。可直接备份已获批准的 Markdown，但移动/分享导出仍需用户指令。

## 多轮反馈与条件归纳

用户已提供实际结果时不重复询问。主观有效可标 user_feedback 下的 SUCCESS，不能升级为 objective_verification；客观指标与主观评价冲突时分别保留，必要时 PARTIAL_SUCCESS / INCONCLUSIVE，不抹除旧失败。

复用前比较目标、输出类型、数据、工具、成本、特殊成功条件和失败原因，说明复用/有条件复用/不复用。相同关键词而数值相反、语义否定或目标不同不构成适用；历史失败原因已消除可重试但解释原因，外部新证据可优于个人旧经验。

多条经验可在会话内形成“条件 X 下方法 Y 曾产生 Z”的候选规律，引用 memory_id/version，保留反例和证据类型；单例只作案例，多例也不证明普遍有效。候选规律不自动持久化、不新建成功记录。用户要求保留时，展示关联经验中拟更新的 constraints/custom_adaptations，保留原结果、关联 ID/版本和历史，经确认用现有 update 提交；不建立独立规律库。
