"""Temporary-data tests of storage behavior, not LLM recommendation quality."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from personal_memory import MarkdownMemory


def experience(status='SUCCESS'):
    return dict(problem_description='志愿者值班安排', problem_abstraction='技能约束下的公平资源分配',
                domain='运筹优化', method_name='整数规划', method_principle='用约束和目标表示分配',
                application_steps=['整理时段', '生成并核查班表'], custom_adaptations=['限制周末差异'],
                constraints=['技能覆盖'], outcome_status=status, feedback='用户反馈已覆盖需求',
                evidence_type='user_feedback', source_references=[], evidence_references=[],
                structure_tags=['资源分配'])


def approve(store, preview):
    return store.commit(preview['proposal'], dict(confirmed=True, user_id=store.user,
                                               digest=preview['approval_digest']))


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'memory'
        self.store = MarkdownMemory('alice', self.root)

    def save(self, status='SUCCESS'):
        return approve(self.store, self.store.preview('save', experience(status)))

    def test_no_approval_no_files(self):
        preview = self.store.preview('save', experience())
        with self.assertRaises(PermissionError):
            self.store.commit(preview['proposal'], {'confirmed': False})
        self.assertFalse(self.root.exists())

    def test_preview_and_empty_read_do_not_write(self):
        self.assertEqual(self.store.records(), [])
        self.store.preview('save', experience())
        self.assertFalse(self.root.exists())

    def test_confirmed_save_is_markdown(self):
        record = self.save()
        files = list(self.root.rglob('*.*'))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].suffix, '.md')
        self.assertTrue(files[0].read_text(encoding='utf-8').startswith('---\n'))
        self.assertEqual(self.store.get(record['memory_id'])['outcome_status'], 'SUCCESS')

    def test_restart_in_new_process(self):
        record = self.save()
        script = Path(__file__).resolve().parents[1] / 'scripts/personal_memory.py'
        result = subprocess.run([sys.executable, str(script), '--user', 'alice', '--root', str(self.root), 'list'],
                                capture_output=True, text=True, encoding='utf-8', env=dict(os.environ, PYTHONUTF8='1'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)[0]['memory_id'], record['memory_id'])

    def test_cli_utf8_independent_of_host_encoding(self):
        record = experience()
        record['feedback'] = '效果良好 🧪'
        approve(self.store, self.store.preview('save', record))
        script = Path(__file__).resolve().parents[1] / 'scripts/personal_memory.py'
        for command, payload in [('list', None), ('search', {'query': '公平资源分配'})]:
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, str(script), '--user', 'alice', '--root', str(self.root), command],
                    input=json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload else None,
                    capture_output=True, env=dict(os.environ, PYTHONUTF8='0', PYTHONIOENCODING='ascii'))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('效果良好 🧪', result.stdout.decode('utf-8'))
                self.assertEqual(len(json.loads(result.stdout.decode('utf-8'))), 1)

    def test_similar_and_unrelated_search(self):
        self.save()
        self.assertEqual(len(self.store.search('公平资源分配')), 1)
        self.assertEqual(self.store.search('火山岩矿物结晶'), [])
        self.assertEqual(len(self.store.search('排班', structure_tags=['资源分配'])), 1)

    def test_failures_and_constraints_retained(self):
        for status in ('SUCCESS', 'PARTIAL_SUCCESS', 'FAILURE'):
            self.save(status)
        hits = self.store.search(structure_tags=['资源分配'])
        self.assertEqual(len(hits), 3)
        self.assertEqual(sum(h['caution'] for h in hits), 2)
        self.assertTrue(all(h['constraints_to_review'] == ['技能覆盖'] for h in hits))
        self.assertTrue(all(h['reuse_status'] == 'requires_agent_review' for h in hits))

    def test_update_preserves_history_and_rejects_stale_approval(self):
        record = self.save()
        changed = experience('FAILURE')
        changed['feedback'] = '新反馈表明周末班未覆盖'
        preview = self.store.preview('update', changed, record['memory_id'])
        updated = approve(self.store, preview)
        self.assertEqual(updated['version'], 2)
        self.assertEqual(updated['history'][0]['outcome_status'], 'SUCCESS')
        self.assertEqual(self.store.get(record['memory_id'])['outcome_status'], 'FAILURE')
        with self.assertRaises(ValueError):
            approve(self.store, preview)

    def test_delete_removes_search_and_history(self):
        record = self.save()
        approve(self.store, self.store.preview('delete', memory_id=record['memory_id']))
        self.assertEqual(self.store.search(structure_tags=['资源分配']), [])
        self.assertEqual(self.store.export()['memories'], [])
        self.assertEqual(list(self.root.rglob('*.md')), [])

    def test_user_isolation_and_wrong_approval(self):
        record = self.save()
        bob = MarkdownMemory('bob', self.root)
        self.assertEqual(bob.records(), [])
        self.assertEqual(bob.search(structure_tags=['资源分配']), [])
        self.assertEqual(bob.export()['memories'], [])
        with self.assertRaises(FileNotFoundError):
            bob.get(record['memory_id'])
        preview = self.store.preview('save', experience())
        with self.assertRaises(PermissionError):
            bob.commit(preview['proposal'], dict(confirmed=True, user_id='bob', digest=preview['approval_digest']))

    @unittest.skipUnless(os.name == 'nt', 'Windows junction regression')
    def test_windows_junction_cannot_redirect_to_another_user(self):
        record = self.save()
        bob = MarkdownMemory('bob', self.root)
        # Paths originate only from TemporaryDirectory and hashed user IDs.
        command = f"New-Item -ItemType Junction -Path '{bob.directory}' -Target '{self.store.directory}' | Out-Null"
        result = subprocess.run(['powershell', '-NoProfile', '-Command', command], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        try:
            with self.assertRaises(ValueError):
                bob.get(record['memory_id'])
            with self.assertRaises(ValueError):
                bob.records()
        finally:
            os.rmdir(bob.directory)

    def test_ai_inference_cannot_claim_observed_outcome(self):
        for status in ('SUCCESS', 'PARTIAL_SUCCESS', 'FAILURE'):
            record = experience(status)
            record['evidence_type'] = 'ai_inference'
            with self.assertRaises(ValueError):
                self.store.preview('save', record)
        self.assertFalse(self.root.exists())

    def test_objective_evidence_required(self):
        record = experience()
        record['evidence_type'] = 'objective_verification'
        with self.assertRaises(ValueError):
            self.store.preview('save', record)

    def test_dedup_and_different_context(self):
        first, second = self.save(), self.save()
        self.assertEqual(first['memory_id'], second['memory_id'])
        record = experience()
        record['constraints'] = ['夜班覆盖']
        approve(self.store, self.store.preview('save', record))
        self.assertEqual(len(self.store.records()), 2)

    def test_modified_proposal_requires_new_approval(self):
        preview = self.store.preview('save', experience())
        changed = copy.deepcopy(preview['proposal'])
        changed['record']['feedback'] = '其他反馈'
        with self.assertRaises(PermissionError):
            self.store.commit(changed, dict(confirmed=True, user_id='alice', digest=preview['approval_digest']))
        self.assertFalse(self.root.exists())

    def test_approval_cannot_be_reused_in_another_directory(self):
        preview = self.store.preview('save', experience())
        other = MarkdownMemory('alice', Path(self.temp.name) / 'other')
        with self.assertRaises(PermissionError):
            approve(other, preview)
        self.assertFalse(other.root.exists())
        self.assertFalse(self.root.exists())

    def test_write_failure_reported_without_partial_record(self):
        with patch('personal_memory.os.replace', side_effect=PermissionError('read-only')):
            with self.assertRaises(PermissionError):
                self.save()
        self.assertEqual(list(self.root.rglob('*.md')), [])
        self.assertEqual(list(self.root.rglob('*.tmp')), [])

    def test_path_traversal_and_skill_directory_rejected(self):
        with self.assertRaises(ValueError):
            self.store.get('../bob')
        with self.assertRaises(ValueError):
            MarkdownMemory('alice', Path(__file__).resolve().parents[1] / 'memory')


if __name__ == '__main__':
    unittest.main(verbosity=2)
