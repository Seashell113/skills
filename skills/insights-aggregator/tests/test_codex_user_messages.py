"""Synthetic schema fixtures only; never read the user's session directories."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPT_DIR))
from collect import SCHEMA_VERSION, codex_parse, compute_meta, format_transcript

A = '11111111-1111-1111-1111-111111111111'
B = '22222222-2222-2222-2222-222222222222'


def row(kind, payload, minute=0):
    stamp = datetime(2026, 10, 15, tzinfo=timezone.utc) + timedelta(minutes=minute)
    return {'timestamp': stamp.isoformat(), 'type': kind, 'payload': payload}


def user(text='synthetic request', *, turn='turn-1', native_id='user-1', minute=0):
    return row('event_msg', {
        'type': 'item_completed', 'thread_id': A, 'turn_id': turn,
        'item': {'type': 'UserMessage', 'id': native_id, 'client_id': 'client-' + str(native_id),
                 'content': [{'type': 'text', 'text': text, 'text_elements': []}]},
        'started_at_ms': 1, 'completed_at_ms': 2,
    }, minute)


def legacy(text='synthetic request', *, turn='turn-1', native_id=None, minute=0):
    payload = {'type': 'user_message', 'message': text}
    if turn is not None:
        payload['turn_id'] = turn
    if native_id is not None:
        payload['id'] = native_id
    return row('event_msg', payload, minute)


def write_rollout(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')


def canonical_rows():
    rows = [row('session_meta', {'id': A, 'cwd': '/synthetic/project'})]
    for index in range(6):
        turn = f'turn-{index}'
        context = row('turn_context', {'turn_id': turn, 'model': 'test-model', 'effort': 'high'}, index)
        rows.extend([context, context])  # Native context replay must not double model counts.
        text = f'synthetic request {index}'
        rows.append(user(text, turn=turn, native_id=f'u-{index}', minute=index))
        rows.append(row('response_item', {'type': 'message', 'role': 'user', 'id': f'mirror-{index}',
                                        'content': [{'type': 'input_text', 'text': text}]}, index))
        if index == 2:
            rows.append(user('synthetic steering', turn=turn, native_id='steering', minute=index))
        for message in range(4):
            ident = f'a-{index}-{message}'
            body = f'synthetic response {index}-{message}'
            rows.append(row('event_msg', {'type': 'item_completed', 'turn_id': turn,
                                         'item': {'type': 'AgentMessage', 'id': ident,
                                                  'content': [{'type': 'text', 'text': body}]}} , index))
            rows.append(row('response_item', {'type': 'message', 'role': 'assistant', 'id': ident,
                                              'content': [{'type': 'output_text', 'text': body}]}, index))
    # Injected response messages remain excluded, including shapes without a known wrapper.
    rows.append(row('response_item', {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'synthetic host configuration'}]}, 5))
    return rows


class CodexUserMessageTests(unittest.TestCase):
    def parse(self, rows):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        path = Path(temp.name) / f'rollout-test-{A}.jsonl'
        write_rollout(path, [row('session_meta', {'id': A}), *rows])
        return codex_parse(path, A)

    def test_new_format_counts_seven_users_twenty_four_assistants_and_six_native_turns(self):
        session = self.parse(canonical_rows()[1:])
        meta = compute_meta(session, {})
        self.assertEqual(meta['user_message_count'], 7)
        self.assertEqual(meta['assistant_message_count'], 24)
        self.assertEqual(meta['models'], {'test-model': 6})
        self.assertEqual(meta['reasoning_effort'], {'high': 6})
        self.assertEqual(meta['first_prompt'], 'synthetic request 0')
        self.assertEqual(format_transcript(session, meta).count('[User]:'), 7)
        self.assertEqual(session.source_audit['owner_leakage_lines'], 0)

    def test_mixed_representations_pair_one_to_one_and_preserve_repeated_messages(self):
        session = self.parse([
            legacy(), user(), legacy(), user(native_id='user-2'), user(native_id='user-2'),
            legacy(turn='turn-2'), user(turn='turn-2', native_id='user-3'),
        ])
        users = [e for e in session.events if e['kind'] == 'user']
        self.assertEqual(len(users), 3)
        self.assertEqual([e['native_id'] for e in users], ['user-1', 'user-2', 'user-3'])

    def test_reverse_order_and_distinct_native_ids_do_not_erase_real_inputs(self):
        self.assertEqual(sum(e['kind'] == 'user' for e in self.parse([user(), legacy()]).events), 1)
        self.assertEqual(sum(e['kind'] == 'user' for e in self.parse([legacy(), legacy()]).events), 2)
        self.assertEqual(sum(e['kind'] == 'user' for e in self.parse([user(), user(native_id='another')]).events), 2)
        self.assertEqual(sum(e['kind'] == 'user' for e in self.parse([legacy(native_id='different'), user()]).events), 2)

    def test_without_turn_identity_only_native_id_can_prove_duplicates(self):
        self.assertEqual(sum(e['kind'] == 'user' for e in self.parse([legacy(turn=None), user(turn=None)]).events), 2)
        self.assertEqual(sum(e['kind'] == 'user' for e in self.parse([user(turn=None), user(turn=None)]).events), 1)

    def test_wrappers_non_text_and_unknown_items_stay_excluded(self):
        malformed = user(); malformed['payload']['item']['content'] = 42
        image = user(); image['payload']['item']['content'] = [{'type': 'image', 'image_url': 'synthetic'}]
        unknown = user(); unknown['payload']['item']['type'] = 'UnknownItem'
        session = self.parse([legacy('<environment_context>synthetic</environment_context>'),
                              user('<permissions>synthetic</permissions>'), user('  '), malformed, image, unknown])
        self.assertEqual(compute_meta(session, {})['user_message_count'], 0)

    def test_foreign_completed_messages_are_excluded(self):
        session = self.parse([row('session_meta', {'id': B}), user('foreign'),
                              row('session_meta', {'id': A}), user('owned')])
        self.assertEqual([e['text'] for e in session.events if e['kind'] == 'user'], ['owned'])

    def test_explicit_foreign_thread_does_not_add_user_or_change_current_turn(self):
        foreign = user('foreign', turn='foreign-turn', native_id='foreign')
        foreign['payload']['thread_id'] = B
        untagged = user('untagged', turn=None, native_id='untagged')
        del untagged['payload']['thread_id']
        session = self.parse([
            user('owned'), foreign, untagged,
            row('response_item', {'type': 'message', 'role': 'assistant',
                                  'content': [{'type': 'output_text', 'text': 'owned reply'}]}),
        ])
        self.assertEqual([e['text'] for e in session.events if e['kind'] == 'user'], ['owned', 'untagged'])
        self.assertEqual({e['turn_id'] for e in session.events}, {'turn-1'})

    def test_frozen_prefix_does_not_read_appended_messages(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / f'rollout-test-{A}.jsonl'
            write_rollout(path, [row('session_meta', {'id': A}), user('first')])
            data = path.read_bytes(); cutoff = len(data); digest = hashlib.sha256(data).hexdigest()
            with path.open('a') as output:
                output.write(json.dumps(user('later', native_id='later', minute=1)) + '\n')
            session = codex_parse(path, A, byte_limit=cutoff, expected_sha256=digest)
            self.assertEqual([e['text'] for e in session.events if e['kind'] == 'user'], ['first'])

    def test_cache_upgrade_requeues_old_codex_facet_without_touching_claude_or_limits(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); home = root / 'insights'; codex = root / 'codex'; claude = root / 'claude'
            rollout = codex / 'sessions' / f'rollout-test-{A}.jsonl'
            write_rollout(rollout, [row('session_meta', {'id': A}), user('one'), user('two', native_id='two', turn='turn-2', minute=2)])
            claude_session = claude / 'projects' / 'synthetic' / 'claude-test.jsonl'
            write_rollout(claude_session, [
                {'type': 'user', 'uuid': 'c-1', 'parentUuid': None, 'timestamp': '2026-10-14T00:00:00Z', 'message': {'role': 'user', 'content': 'first synthetic task'}},
                {'type': 'user', 'uuid': 'c-2', 'parentUuid': 'c-1', 'timestamp': '2026-10-14T00:02:00Z', 'message': {'role': 'user', 'content': 'second synthetic task'}},
            ])
            args = [sys.executable, str(SCRIPT_DIR / 'collect.py'), '--home', str(home), '--codex-dir', str(codex), '--claude-dir', str(claude), '--days', '0', '--max-facets', '2']
            def run(extra=()):
                return json.loads(subprocess.run([*args, *extra], check=True, capture_output=True, text=True).stdout)
            run()
            meta_path = home / 'cache/meta/codex' / f'{A}.json'
            stale_meta = json.loads(meta_path.read_text()); stale_meta.update(schema_version=11, user_message_count=0)
            meta_path.write_text(json.dumps(stale_meta))
            facet_path = home / 'cache/facets/codex' / f'{A}.json'
            facet_path.write_text(json.dumps({'_user_message_count': 1, 'brief_summary': 'stale synthetic facet'}))
            claude_facet = home / 'cache/facets/claude-code/claude-test.json'
            claude_bytes = json.dumps({'_user_message_count': 2, 'brief_summary': 'retained synthetic facet'})
            claude_facet.write_text(claude_bytes)
            result = run()
            self.assertEqual(json.loads(meta_path.read_text())['user_message_count'], 2)
            self.assertEqual(json.loads(meta_path.read_text())['schema_version'], SCHEMA_VERSION)
            pending = json.loads((home / 'work/pending_facets.json').read_text())
            self.assertEqual([(p['agent'], p['session_id']) for p in pending], [('codex', A)])
            self.assertEqual(pending[0]['parser_schema_version'], SCHEMA_VERSION)
            self.assertEqual(result['facets_already_cached'], 1)
            self.assertEqual(claude_facet.read_text(), claude_bytes)
            self.assertEqual(json.loads(facet_path.read_text())['_user_message_count'], 1)  # No model or cache overwrite.
            self.assertEqual(run(['--max-facets', '0'])['pending_facets'], 0)
            # A new-parser facet is reusable even if message growth is below the resume threshold.
            facet_path.write_text(json.dumps({'_user_message_count': 2, '_parser_schema_version': SCHEMA_VERSION}))
            self.assertEqual(run()['pending_facets'], 0)
            # Out-of-window data is never requeued by the schema migration.
            rollout.write_text(rollout.read_text().replace('2026-10-15', '2000-01-01'))
            facet_path.write_text(json.dumps({'_user_message_count': 0}))
            self.assertEqual(run(['--days', '1'])['pending_facets'], 0)

    def test_aggregation_ignores_stale_semantics_after_failed_or_capped_refresh(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); home = root / 'insights'; codex = root / 'codex'; claude = root / 'claude'
            rollout = codex / 'sessions' / f'rollout-test-{A}.jsonl'
            write_rollout(rollout, [row('session_meta', {'id': A}), user('real request'),
                                    user('real followup', native_id='two', turn='turn-2', minute=2)])
            write_rollout(claude / 'projects/synthetic/claude-test.jsonl', [
                {'type': 'user', 'uuid': 'c-1', 'parentUuid': None, 'timestamp': '2026-10-14T00:00:00Z',
                 'message': {'role': 'user', 'content': 'first request'}},
                {'type': 'user', 'uuid': 'c-2', 'parentUuid': 'c-1', 'timestamp': '2026-10-14T00:02:00Z',
                 'message': {'role': 'user', 'content': 'second request'}},
            ])
            collect_args = [sys.executable, str(SCRIPT_DIR / 'collect.py'), '--home', str(home),
                            '--codex-dir', str(codex), '--claude-dir', str(claude), '--days', '0']
            aggregate_args = [sys.executable, str(SCRIPT_DIR / 'aggregate.py'), '--home', str(home), '--days', '0']
            def run(args):
                return json.loads(subprocess.run(args, check=True, capture_output=True, text=True).stdout)
            run(collect_args)
            base_facet = {'underlying_goal': 'goal', 'outcome': 'fully_achieved', 'brief_summary': 'summary',
                          'goal_categories': {'coding': 1}, 'user_satisfaction_counts': {}, 'friction_counts': {}}
            codex_facet = home / 'cache/facets/codex' / f'{A}.json'
            claude_facet = home / 'cache/facets/claude-code/claude-test.json'
            claude_bytes = json.dumps({**base_facet, 'agent': 'claude-code', 'session_id': 'claude-test',
                                      '_user_message_count': 2, 'brief_summary': 'valid Claude summary'})
            claude_facet.write_text(claude_bytes)
            for cap in (0, 1):
                for old_schema in (None, SCHEMA_VERSION - 1):
                    for categories in ({'coding': 1}, {'warmup_minimal': 1}):
                        with self.subTest(cap=cap, old_schema=old_schema, categories=categories):
                            stale = {**base_facet, 'agent': 'codex', 'session_id': A,
                                     '_user_message_count': 0, 'brief_summary': 'STALE SUMMARY',
                                     'goal_categories': categories}
                            if old_schema is not None:
                                stale['_parser_schema_version'] = old_schema
                            stale_bytes = json.dumps(stale); codex_facet.write_text(stale_bytes)
                            collection = run([*collect_args, '--max-facets', str(cap)])
                            self.assertEqual(collection['pending_facets'], cap)
                            # Deliberately do not execute pending work, as when facet extraction fails.
                            result = run(aggregate_args)
                            aggregated = json.loads((home / 'work/aggregated.json').read_text())
                            self.assertEqual(result['sessions_after_filter'], 2)
                            self.assertEqual(result['facets_used'], 1)
                            self.assertEqual(result['stale_codex_facets_ignored'], 1)
                            self.assertEqual(aggregated['combined']['total_messages'], 4)
                            self.assertNotIn('STALE SUMMARY', (home / 'work/insight-context.md').read_text())
                            self.assertEqual(codex_facet.read_text(), stale_bytes)
                            self.assertEqual(claude_facet.read_text(), claude_bytes)
            codex_facet.write_text(json.dumps({**base_facet, 'agent': 'codex', 'session_id': A,
                                              '_user_message_count': 2, '_parser_schema_version': SCHEMA_VERSION}))
            result = run(aggregate_args)
            self.assertEqual(result['sessions_after_filter'], 2)
            self.assertEqual(result['facets_used'], 2)
            self.assertEqual(result['stale_codex_facets_ignored'], 0)


if __name__ == '__main__':
    unittest.main()
