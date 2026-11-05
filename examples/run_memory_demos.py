"""Synthetic public demos of the actual Markdown adapter, never real personal memory."""
import copy
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from personal_memory import MarkdownMemory

OUT = ROOT / 'demo-output'
CLI = ROOT / 'scripts/personal_memory.py'


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def cli(root, user, command, payload=None):
    proc = subprocess.run([sys.executable, str(CLI), '--root', str(root), '--user', user, command],
                          input=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
                          capture_output=True, encoding='utf-8')
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    return json.loads(proc.stdout)


def record(problem, abstraction, method, principle, steps, constraints, status, feedback, evidence, tags):
    return dict(problem_description=problem, problem_abstraction=abstraction, domain='合成演示',
                method_name=method, method_principle=principle, application_steps=steps,
                custom_adaptations=[], constraints=constraints, outcome_status=status,
                feedback=feedback, evidence_type=evidence, evidence_references=[],
                source_references=[], structure_tags=tags)


def main():
    OUT.mkdir(exist_ok=True)
    # Small task executed here; objectives and checker are separate from the store.
    availability = {'A': {0, 2}, 'B': {0, 1}, 'C': {1, 2}}
    feasible = [p for p in itertools.product('ABC', repeat=3)
                if all(day in availability[person] for day, person in enumerate(p))
                and len(set(p)) == 3]
    assert feasible
    schedule = list(feasible[0])
    assert all(day in availability[person] for day, person in enumerate(schedule))
    assert all(schedule.count(person) == 1 for person in 'ABC')
    prediction = sum([10, 10, 10]) / 3
    actual = [30, 30]
    mae = sum(abs(prediction - x) for x in actual) / len(actual)
    assert mae == 20 and mae > 5
    tasks = [
        ('01-scheduling', record('三天值班安排需要满足可用时间且每人一次', '带可用性限制的公平资源分配',
            '枚举可行分配并检查约束', '先排除不可用组合，再检查覆盖与负担',
            ['列出可用时段', '枚举三天分配', '逐条检查覆盖及每人一次'],
            ['三名人员三天', '每人一次', '仅安排可用时段'], 'SUCCESS',
            '合成任务实际计算：可行安排通过全部约束检查，不代表真实团队反馈',
            'objective_verification', ['资源分配', '值班']),
         dict(schedule=schedule, availability={k: sorted(v) for k, v in availability.items()},
              checked=['daily coverage', 'availability', 'one shift per person']),
         '现在增加夜班，但A没有夜班资质。能照搬旧班表吗？',
         '不直接复用旧班表；保留约束建模思路，增加夜班资质约束后重新求解。'),
        ('02-forecast-failure', record('需求突然跃升时旧均值预测没有跟上', '结构变化下的短期预测',
            '固定历史三点均值基线', '用训练期最后三点均值作为固定预测',
            ['训练期为四个10', '固定预测两个留出点', '计算MAE并对照预设阈值5'],
            ['预测期分布接近训练期', '验收MAE不超过5'], 'FAILURE',
            '合成留出实验实际MAE=20，大于预设阈值5，失败；不说明该方法普遍无效',
            'objective_verification', ['时间序列', '需求预测']),
         dict(train=[10, 10, 10, 10], test=actual, predictions=[prediction, prediction],
              mae=mae, acceptance_mae=5),
         '新一轮促销让需求同样突然跳升，直接沿用这个均值法好吗？',
         '历史失败条件再次出现，不把固定旧均值作为已验证有效推荐；先处理变化并重新回测。'),
        ('03-training-partial', record('培训理解反馈改善但测验成绩未提高', '理解感受与任务结果不一致的培训改进',
            '分段文字复述', '阅读短段后用自己的话复述并对照要点',
            ['模拟场景中阅读短段', '模拟场景中文字复述', '模拟场景中对照要点'],
            ['允许文字回答', '可提供文字反馈'], 'PARTIAL_SUCCESS',
            '仅合成反馈夹具：学员说更容易理解，但测验成绩未提高。并非真实用户研究',
            'user_feedback', ['培训', '主动回忆']),
         dict(type='synthetic_feedback_fixture', actual_participants=0,
              feedback='更容易理解，但测验成绩未提高'),
         '接下来只能单向发通知，不允许收集回答，也没有反馈渠道，能直接复用吗？',
         '不能直接复用需要作答和反馈的完整流程；部分成功也不能解释为成绩提升。'),
    ]
    results = []
    for name, content, task_evidence, next_problem, decision in tasks:
        case_dir = OUT / name
        case_dir.mkdir(exist_ok=True)
        evidence_path = case_dir / 'task_evidence.json'
        dump(evidence_path, task_evidence)
        if content['evidence_type'] == 'objective_verification':
            content['evidence_references'] = [str(evidence_path.resolve())]
        with tempfile.TemporaryDirectory(prefix='dmf-public-demo-') as temporary:
            memory_root = Path(temporary) / 'memory'
            user = 'synthetic-demo-user'
            store = MarkdownMemory(user, memory_root)
            preview = store.preview('save', content)
            assert not memory_root.exists()
            try:
                store.commit(preview['proposal'], {'confirmed': False, 'user_id': user,
                                                   'digest': preview['approval_digest']})
            except PermissionError:
                pass
            else:
                raise AssertionError('Unapproved write accepted')
            assert not memory_root.exists()
            # Test fixture approval, never presented as actual end-user feedback/consent.
            approval = dict(confirmed=True, user_id=user, digest=preview['approval_digest'])
            saved = store.commit(preview['proposal'], approval)
            ident = saved['memory_id']
            markdown = next(store.directory.glob('*.md')).read_text(encoding='utf-8')
            (case_dir / 'approved-synthetic-snapshot.md').write_text(markdown, encoding='utf-8')
            assert len(list(store.directory.glob('*.md'))) == 1
            again = store.commit(preview['proposal'], approval)
            assert again['memory_id'] == ident and len(store.records()) == 1
            restarted = cli(memory_root, user, 'get', dict(memory_id=ident))
            assert restarted['memory_id'] == ident and restarted['version'] == 1
            hits = cli(memory_root, user, 'search', dict(query=content['problem_abstraction'],
                       structure_tags=content['structure_tags'], constraints=['新条件']))
            assert any(h['record']['memory_id'] == ident for h in hits)
            assert all(h['reuse_status'] == 'requires_agent_review' for h in hits)
            if content['outcome_status'] != 'SUCCESS':
                assert hits[0]['caution'] is True
            assert cli(memory_root, 'different-synthetic-user', 'list') == []
            changed = copy.deepcopy(content)
            changed['custom_adaptations'] = ['模拟后续反馈：新增条件必须重新核对，不外推效果']
            update = store.preview('update', changed, ident)
            updated = store.commit(update['proposal'], dict(confirmed=True, user_id=user,
                                   digest=update['approval_digest']))
            assert updated['version'] == 2 and updated['history'][0]['version'] == 1
            exported = cli(memory_root, user, 'export')
            assert len(exported['memories']) == 1
            dump(case_dir / 'approved-synthetic-export.json', exported)
            deletion = store.preview('delete', memory_id=ident)
            store.commit(deletion['proposal'], dict(confirmed=True, user_id=user,
                         digest=deletion['approval_digest']))
            assert cli(memory_root, user, 'list') == []
            assert cli(memory_root, user, 'search', dict(query=content['problem_abstraction'],
                       structure_tags=content['structure_tags'])) == []
            assert not list(store.directory.glob('*.md'))
            result = dict(case=name, outcome_status=content['outcome_status'],
                checks=dict(preview_no_write=True, denied_approval_no_write=True,
                    confirmed_markdown=True, exact_dedup=True, new_process_read=True,
                    new_process_retrieval=True, failure_caution=(content['outcome_status'] != 'SUCCESS'),
                    other_user_empty=True, update_history=True, export=True,
                    deletion_file_removed=True, new_process_after_delete_empty=True),
                next_problem=next_problem, agent_reuse_review=decision,
                semantic_review='root qualitative judgment; not an independent automatic test',
                approval='synthetic fixture confirmation; not a real user event',
                deletion_scope='live temporary memory and embedded history removed; explicit public synthetic snapshots retained')
            dump(case_dir / 'results.json', result)
            results.append(result)
    dump(OUT / 'results.json', dict(cases=results, real_personal_memory_used=False,
         limitations=['process restart tested, not independent Agent automatic behavior',
                      'synthetic data and simulated consent, not real user outcome study',
                      'semantic reuse reviewed by root, not enforced by lexical search']))
    print(json.dumps(dict(cases=len(results), result='all executed storage assertions passed',
                         output=str(OUT)), ensure_ascii=False))


if __name__ == '__main__':
    main()
