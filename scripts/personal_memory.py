"""Markdown memory adapter and JSON CLI. Requires Python 3.10+ and PyYAML."""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

TEXT = {'problem_description', 'problem_abstraction', 'domain', 'method_name',
        'method_principle', 'feedback', 'evidence_type', 'outcome_status'}
LISTS = {'application_steps', 'custom_adaptations', 'constraints',
         'source_references', 'structure_tags', 'evidence_references'}
STATUSES = {'UNVERIFIED', 'SUCCESS', 'PARTIAL_SUCCESS', 'FAILURE', 'INCONCLUSIVE'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def validate(record):
    if not isinstance(record, dict) or set(record) != TEXT | LISTS:
        raise ValueError(f'Required fields: {sorted(TEXT | LISTS)}')
    for field in TEXT:
        if not isinstance(record[field], str) or not record[field].strip():
            raise ValueError(f'Nonempty text required: {field}')
    for field in LISTS:
        if not isinstance(record[field], list) or any(not isinstance(x, str) or not x.strip() for x in record[field]):
            raise ValueError(f'String list required: {field}')
    if record['outcome_status'] not in STATUSES:
        raise ValueError('Invalid outcome_status')
    if record['evidence_type'] not in {'user_feedback', 'objective_verification', 'ai_inference', 'none'}:
        raise ValueError('Invalid evidence_type')
    if record['outcome_status'] in {'SUCCESS', 'PARTIAL_SUCCESS', 'FAILURE'}:
        if record['evidence_type'] not in {'user_feedback', 'objective_verification'} or not record['application_steps']:
            raise ValueError('Observed outcome requires real feedback/evidence and actual steps')
    if record['evidence_type'] == 'objective_verification' and not record['evidence_references']:
        raise ValueError('Objective verification requires locatable evidence')


def terms(text):
    text = text.casefold()
    result = set(re.findall(r'[a-z0-9]+', text))
    for run in re.findall(r'[\u4e00-\u9fff]+', text):
        result.update(run[i:i + 2] for i in range(len(run) - 1))
    return result


def default_root():
    configured = os.environ.get('DOMAIN_METHOD_MEMORY_HOME')
    return Path(configured).expanduser() if configured else Path.home() / '.local/share/domain-method-finder/memory'


class MarkdownMemory:
    """Single-writer adapter; authenticated identity and genuine consent belong to host."""

    def __init__(self, user_id, root=None):
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError('Host-bound user_id required')
        self.user = user_id
        self.root = (Path(root).expanduser() if root is not None else default_root()).resolve()
        if self.root.is_relative_to(Path(__file__).resolve().parents[1]):
            raise ValueError('Memory must be outside Skill installation directory')
        self.directory = self.root / hashlib.sha256(user_id.encode()).hexdigest()

    def _path(self, memory_id):
        if not isinstance(memory_id, str) or str(uuid.UUID(memory_id)) != memory_id:
            raise ValueError('Canonical UUID required')
        path = self.directory / f'{memory_id}.md'
        if self.directory.resolve() != self.directory or path.is_symlink() or path.resolve().parent != self.directory:
            raise ValueError('Memory path escapes user directory or contains symlink')
        return path

    def get(self, memory_id):
        path = self._path(memory_id)
        match = re.match(r'\A---\r?\n(.*?)\r?\n---\r?\n', path.read_text(encoding='utf-8'), re.S)
        if not match:
            raise ValueError(f'Invalid frontmatter: {path.name}')
        record = yaml.safe_load(match[1])
        if not isinstance(record, dict) or record.get('memory_id') != memory_id:
            raise ValueError('Memory ID mismatch')
        validate({k: record[k] for k in TEXT | LISTS})
        return record

    def records(self):
        if self.directory.resolve() != self.directory:
            raise ValueError('Symlink user directories are not allowed')
        return [self.get(p.stem) for p in sorted(self.directory.glob('*.md'))]

    def preview(self, operation, record=None, memory_id=None):
        if operation not in {'save', 'update', 'delete'}:
            raise ValueError('Unknown operation')
        if operation != 'delete':
            validate(record)
        if operation != 'save' and not memory_id:
            raise ValueError('memory_id required')
        if operation == 'save' and memory_id:
            raise ValueError('save allocates a new ID')
        current = self.get(memory_id) if memory_id else None
        proposal = dict(operation=operation, user_id=self.user, storage_root=str(self.root), record=record,
                        memory_id=memory_id, current=current)
        return dict(proposal=proposal, approval_digest=digest(proposal))

    def commit(self, proposal, approval):
        # Validate consent before creating even a directory or temporary file.
        if (not isinstance(approval, dict) or approval.get('confirmed') is not True
                or approval.get('user_id') != self.user or proposal.get('user_id') != self.user
                or proposal.get('storage_root') != str(self.root)
                or approval.get('digest') != digest(proposal)):
            raise PermissionError('Explicit approval bound to this preview and user required')
        fresh = self.preview(proposal['operation'], proposal['record'], proposal['memory_id'])
        if fresh['proposal'] != proposal:
            raise ValueError('Stale preview: review and confirm again')
        if proposal['operation'] == 'delete':
            self._path(proposal['memory_id']).unlink()
            return {'deleted': proposal['memory_id']}
        content = proposal['record']
        if proposal['operation'] == 'save':
            for existing in self.records():
                if {k: existing[k] for k in TEXT | LISTS} == content:
                    return existing
        old = proposal['current']
        now = datetime.now(timezone.utc).isoformat()
        history = []
        if old:
            history = old.get('history', []) + [{k: v for k, v in old.items() if k != 'history'}]
        result = dict(content, memory_id=old['memory_id'] if old else str(uuid.uuid4()),
                      created_at=old['created_at'] if old else now, updated_at=now,
                      version=old['version'] + 1 if old else 1, history=history)
        path = self._path(result['memory_id'])
        body = '---\n' + yaml.safe_dump(result, allow_unicode=True, sort_keys=False) + '---\n\n'
        body += '# 方法经验\n\n完整经验与历史版本见上方 YAML。\n'
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.', suffix='.tmp', dir=self.directory)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return result

    def search(self, query='', structure_tags=None, constraints=None, limit=10):
        if not 1 <= limit <= 100:
            raise ValueError('limit must be 1..100')
        query_terms, tags = terms(query), set(structure_tags or [])
        hits = []
        for record in self.records():
            text = ' '.join(record[k] for k in ('problem_description', 'problem_abstraction', 'method_name', 'domain'))
            overlap = query_terms & terms(text)
            ratio = len(overlap) / max(1, len(query_terms))
            matched = sorted(tags & set(record['structure_tags']))
            if not matched and not (len(overlap) >= 2 and ratio >= .3):
                continue
            hits.append(dict(record=record, matched_structure_tags=matched, lexical_overlap=round(ratio, 3),
                             constraints_to_review=sorted(set(record['constraints']) - set(constraints or [])),
                             caution=record['outcome_status'] in {'FAILURE', 'PARTIAL_SUCCESS'},
                             reuse_status='requires_agent_review'))
        hits.sort(key=lambda h: (len(h['matched_structure_tags']), h['lexical_overlap']), reverse=True)
        return hits[:limit]

    def export(self):
        return {'schema_version': 1, 'memories': self.records()}


def main():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', help='Persistent directory outside Skill')
    parser.add_argument('--user', required=True, help='Identity supplied by trusted host')
    parser.add_argument('command', choices=['preview', 'commit', 'list', 'get', 'search', 'export'])
    args = parser.parse_args()
    try:
        store = MarkdownMemory(args.user, args.root)
        payload = json.load(sys.stdin) if args.command in {'preview', 'commit', 'get', 'search'} else {}
        commands = {'preview': store.preview, 'commit': store.commit, 'list': store.records,
                    'get': store.get, 'search': store.search, 'export': store.export}
        print(json.dumps(commands[args.command](**payload), ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, yaml.YAMLError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
