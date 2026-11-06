"""Only synthetic local fixtures: activity windows never inspect real user data."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from collect import SCHEMA_VERSION, analysis_window, codex_parse, codex_scan, compute_meta, project_window

A = '11111111-1111-1111-1111-111111111111'
B = '22222222-2222-2222-2222-222222222222'
SINCE = '2026-10-15T00:00:00Z'
AS_OF = '2026-10-16T00:00:00Z'
WINDOW = analysis_window(since=SINCE, as_of=AS_OF)
ZSTD = shutil.which('zstd') or ('/opt/homebrew/bin/zstd' if Path('/opt/homebrew/bin/zstd').exists() else None)


def row(kind, payload, stamp):
    return {'type': kind, 'payload': payload, 'timestamp': stamp}


def user(text, stamp, turn='user-turn'):
    return row('event_msg', {'type': 'user_message', 'message': text, 'turn_id': turn}, stamp)


def context(model, stamp, turn='user-turn', effort='high'):
    return row('turn_context', {'turn_id': turn, 'model': model, 'effort': effort}, stamp)


def tool(name, stamp):
    return row('response_item', {'type': 'function_call', 'name': name,
                                'arguments': '{}', 'call_id': name}, stamp)


def data(rows):
    return ''.join(json.dumps(item) + '\n' for item in rows).encode()


def fixture_rows():
    return [row('session_meta', {'id': A, 'cwd': '/synthetic/project', 'thread_source': 'user'},
                '2026-01-01T00:00:00Z'),
            user('past task', '2026-01-01T00:00:01Z', 'past'),
            context('past-model', SINCE, 'past'), user('exclusive boundary', SINCE, 'boundary'),
            tool('outside-past-tool', SINCE),
            user('one short resumed task', '2026-10-15T12:00:00Z'),
            context('window-model', '2026-10-15T12:00:00Z'),
            context('window-model', '2026-10-15T12:00:01Z'),
            context('codex-auto-review', '2026-10-15T12:00:02Z', 'review', 'low'),
            tool('window-tool', AS_OF),
            context('future-model', '2026-10-16T00:00:01Z', 'future'),
            user('future request', '2026-10-16T00:00:01Z', 'future'),
            tool('outside-future-tool', '2026-10-16T00:00:01Z')]


class ActivityWindowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / 'home'
        self.codex = self.root / 'codex'
        self.path = self.codex / 'sessions' / f'rollout-synthetic-{A}.jsonl'
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(data(fixture_rows()))

    def collect(self, *, since=SINCE, as_of=AS_OF, cap=0, extra=()):
        command = [sys.executable, str(SCRIPTS / 'collect.py'), '--home', str(self.home),
                   '--claude-dir', str(self.root / 'no-claude'), '--codex-dir', str(self.codex),
                   '--since', since, '--as-of', as_of, '--max-facets', str(cap), *extra]
        return json.loads(subprocess.run(command, check=True, capture_output=True, text=True).stdout)

    def aggregate(self, extra=()):
        subprocess.run([sys.executable, str(SCRIPTS / 'aggregate.py'), '--home', str(self.home),
                        '--since', SINCE, '--as-of', AS_OF, *extra],
                       check=True, capture_output=True, text=True)
        return json.loads((self.home / 'work/aggregated.json').read_text())

    def meta(self):
        return json.loads((self.home / f'cache/meta/codex/{A}.json').read_text())

    def test_resume_and_single_user_count_without_boundary_leakage(self):
        summary = self.collect()
        self.assertEqual(summary['root_sessions_in_window'], 1)
        self.assertEqual(summary['pending_facets'], 0)
        meta = self.meta()
        self.assertEqual(meta['user_message_count'], 1)
        self.assertEqual(meta['models'], {'window-model': 1})
        self.assertEqual(meta['reasoning_effort'], {'high': 1})
        self.assertEqual(meta['tool_counts'], {'window-tool': 1})
        self.assertEqual(meta['analysis_window'], WINDOW)
        self.assertFalse(meta['window_covers_session'])
        self.assertEqual(meta['first_prompt'], 'one short resumed task')
        aggregated = self.aggregate()
        self.assertEqual(aggregated['combined']['total_sessions'], 1)
        self.assertEqual(aggregated['combined']['total_messages'], 1)
        self.assertEqual(aggregated['combined']['models'], {'window-model': 1})
        self.assertEqual(aggregated['window']['bounds'], '(since, as_of]')

    def test_no_user_in_window_does_not_become_root_from_tool_tail(self):
        self.path.write_bytes(data([row('session_meta', {'id': A}, '2026-01-01T00:00:00Z'),
                                   user('old task', SINCE), tool('window-tail', AS_OF)]))
        self.collect()
        self.assertEqual(self.aggregate()['combined']['total_sessions'], 0)

    def test_fork_cache_tracks_parent_dependency_without_child_changes(self):
        parent = self.path.with_name(f'rollout-parent-{B}.jsonl')
        copied = [context('parent-model', AS_OF, 'parent-native'),
                  user('inherited', AS_OF, 'parent-native')]
        parent.write_bytes(data([row('session_meta', {'id': B}, SINCE), *copied]))
        self.path.write_bytes(data([row('session_meta', {'id': A, 'forked_from_id': B}, SINCE),
                                    *copied, user('new task', AS_OF, 'child-native')]))
        self.collect()
        self.assertEqual(self.meta()['user_message_count'], 1)
        self.assertEqual(self.collect()['from_cache'], 2)
        with parent.open('ab') as handle:
            handle.write(data([user('parent later activity', AS_OF, 'parent-later')]))
        self.assertEqual(self.collect()['parsed_now'], 2)
        self.assertEqual(self.meta()['user_message_count'], 1)
        parent.unlink()
        summary = self.collect()
        self.assertEqual(summary['parsed_now'], 1)
        self.assertEqual(self.meta()['source_audit']['fork_history']['status'],
                         'parent_source_unavailable')
        self.assertEqual(summary['codex_ownership']['fork_lineage_unverified'][0]['session_id'], A)

    def test_window_cache_recompute_and_aggregate_does_not_reuse_wrong_window(self):
        self.collect()
        self.assertEqual(self.collect()['from_cache'], 1)
        other = self.collect(since=AS_OF, as_of='2026-10-17T00:00:00Z')
        self.assertEqual(other['parsed_now'], 1)
        self.assertEqual(self.meta()['models'], {'future-model': 1})
        old_window = self.aggregate()
        self.assertEqual(old_window['combined']['total_sessions'], 0)
        self.assertEqual(old_window['mismatched_window_metas_ignored'], 1)
        self.collect()
        # No flags after collect inherits the exact frozen instant (default days agrees).
        subprocess.run([sys.executable, str(SCRIPTS / 'aggregate.py'), '--home', str(self.home)],
                       check=True, capture_output=True, text=True)
        self.assertEqual(json.loads((self.home / 'work/aggregated.json').read_text())['combined']['total_sessions'], 1)

    def test_partial_lifecycle_facets_are_ignored_and_window_stamp_requeues(self):
        rows = fixture_rows() + [user('window followup', '2026-10-15T13:00:00Z', 'followup')]
        self.path.write_bytes(data(rows))
        self.collect()
        facet_path = self.home / f'cache/facets/codex/{A}.json'
        facet = {'agent': 'codex', 'session_id': A, '_parser_schema_version': SCHEMA_VERSION,
                 '_user_message_count': 2, 'underlying_goal': 'synthetic goal',
                 'outcome': 'fully_achieved', 'brief_summary': 'old lifecycle summary',
                 'goal_categories': {'warmup_minimal': 1}, 'user_satisfaction_counts': {}, 'friction_counts': {}}
        for stamp in (None, analysis_window(since='2026-01-01', as_of=AS_OF)):
            candidate = dict(facet)
            if stamp:
                candidate['_analysis_window'] = stamp
            encoded = json.dumps(candidate)
            facet_path.write_text(encoded)
            self.assertEqual(self.collect(cap=1)['pending_facets'], 1)
            aggregated = self.aggregate()
            self.assertEqual(aggregated['combined']['total_sessions'], 1)
            self.assertEqual(aggregated['combined']['sessions_with_facets'], 0)
            self.assertEqual(aggregated['stale_window_facets_ignored'], 1)
            self.assertEqual(facet_path.read_text(), encoded)
        facet['_analysis_window'] = WINDOW
        facet_path.write_text(json.dumps(facet))
        self.assertEqual(self.collect(cap=1)['pending_facets'], 0)
        self.assertEqual(self.aggregate()['combined']['sessions_with_facets'], 1)
        transcript = (self.home / f'transcripts/codex/{A}.txt').read_text()
        self.assertIn('window followup', transcript)
        self.assertNotIn('past task', transcript)
        self.assertNotIn('future request', transcript)
        pending = json.loads((self.home / 'work/pending_facets.json').read_text())
        self.assertEqual(pending, [])

    def test_legacy_lifecycle_meta_crossing_window_is_rejected(self):
        self.collect()
        meta = self.meta()
        del meta['analysis_window']
        meta['start_time'] = '2026-01-01T00:00:00Z'
        (self.home / f'cache/meta/codex/{A}.json').write_text(json.dumps(meta))
        aggregated = self.aggregate()
        self.assertEqual(aggregated['mismatched_window_metas_ignored'], 1)
        self.assertEqual(aggregated['combined']['total_sessions'], 0)

    def test_cumulative_tokens_subtract_pre_window_baseline_and_ignore_replays(self):
        def tokens(stamp, total, last=None):
            info = {'total_token_usage': total}
            if last is not None:
                info['last_token_usage'] = last
            return row('event_msg', {'type': 'token_count', 'info': info}, stamp)
        baseline = {'input_tokens': 100, 'cached_input_tokens': 20, 'output_tokens': 30}
        current = {'input_tokens': 160, 'cached_input_tokens': 30, 'output_tokens': 55}
        rows = [row('session_meta', {'id': A}, '2026-01-01T00:00:00Z'),
                tokens(SINCE, baseline), user('task', '2026-10-15T01:00:00Z'),
                tokens('2026-10-15T01:01:00Z', current),
                tokens('2026-10-15T01:02:00Z', current),
                tokens('2026-10-17T00:00:00Z', {'input_tokens': 500, 'output_tokens': 200})]
        self.path.write_bytes(data(rows))
        self.collect()
        self.assertEqual(self.meta()['input_tokens'], 50)
        self.assertEqual(self.meta()['output_tokens'], 25)
        self.assertEqual(self.meta()['token_usage_missing_events'], 0)
        # A first in-window cumulative total without baseline cannot be assigned.
        self.path.write_bytes(data([rows[0], rows[2], rows[3]]))
        self.collect()
        self.assertEqual(self.meta()['input_tokens'], 0)
        self.assertEqual(self.meta()['token_usage_missing_events'], 1)
        self.assertEqual(self.aggregate()['combined']['token_usage_missing_events'], 1)

    def test_internal_activity_without_user_is_kept_separate(self):
        self.path.write_bytes(data([row('session_meta', {'id': A, 'thread_source': 'subagent'}, SINCE),
                                   context('worker-model', AS_OF)]))
        self.collect()
        aggregated = self.aggregate()
        self.assertEqual(aggregated['combined']['total_sessions'], 0)
        self.assertEqual(aggregated['internal_sessions_excluded'], 1)
        self.assertEqual(aggregated['internal_model_effort']['models'], {'worker-model': 1})

    def test_orchestration_is_counted_without_guessing_nested_javascript(self):
        rows = [row('session_meta', {'id': A}, SINCE),
                user('synthetic task', '2026-10-15T01:00:00Z'),
                context('test-model', '2026-10-15T01:00:00Z')]
        javascript = 'await tools.exec_command({cmd: "git commit -m synthetic"}); await tools.apply_patch("*** Add File: nested.py\\n+print(1)")'
        for index, name in enumerate(('functions.exec', 'exec', 'functions__exec', 'functions_exec')):
            rows.append(row('response_item', {'type': 'custom_tool_call', 'name': name,
                                              'input': javascript, 'call_id': f'wrapper-{index}'}, AS_OF))
        # A direct call still contributes observed metrics independently.
        rows.append(row('response_item', {'type': 'function_call', 'name': 'exec_command',
                                          'arguments': json.dumps({'cmd': 'git commit -m direct'}),
                                          'call_id': 'direct'}, AS_OF))
        self.path.write_bytes(data(rows))
        self.collect()
        meta = self.meta()
        self.assertEqual(meta['tool_category_counts'], {'orchestration': 4, 'shell': 1})
        self.assertEqual(meta['tool_wrapped_calls'], 4)
        self.assertEqual(meta['git_commits'], 1)
        self.assertEqual(meta['lines_added'], 0)
        self.assertEqual(meta['languages'], {})
        self.assertEqual(meta['user_message_count'], 1)
        self.assertEqual(meta['models'], {'test-model': 1})
        self.assertTrue(meta['metric_coverage']['has_unparsed_wrapped_calls'])
        self.assertEqual(meta['metric_coverage']['tool_counts'], 'top_level_records')
        self.assertEqual(meta['metric_coverage']['languages'], 'direct_calls_only')
        group = self.aggregate()['combined']
        self.assertEqual(group['tool_wrapped_calls'], 4)
        self.assertEqual(group['metric_coverage'], meta['metric_coverage'])
        # Schema 14 invalidates the prior cached run even with unchanged sources.
        meta['schema_version'] = 13
        del meta['tool_wrapped_calls']
        (self.home / f'cache/meta/codex/{A}.json').write_text(json.dumps(meta))
        self.assertEqual(self.collect()['parsed_now'], 1)
        self.assertEqual(self.meta()['schema_version'], SCHEMA_VERSION)
        self.assertEqual(self.meta()['tool_wrapped_calls'], 4)

    def test_date_hour_and_cache_use_one_explicit_display_timezone(self):
        self.path.write_bytes(data([row('session_meta', {'id': A}, SINCE),
                                   user('before UTC midnight', '2026-10-15T23:50:00Z'),
                                   user('at UTC midnight', AS_OF, 'second')]))
        self.collect(extra=['--timezone', 'Asia/Shanghai'])
        meta = self.meta()
        self.assertEqual(meta['message_hours'], [7, 8])
        self.assertEqual(meta['message_dates'], ['2026-10-16', '2026-10-16'])
        self.assertEqual(meta['display_timezone']['name'], 'Asia/Shanghai')
        self.assertEqual(meta['display_timezone']['utc_offset'], '+0800')
        aggregate = self.aggregate()
        self.assertEqual(aggregate['display_timezone'], meta['display_timezone'])
        self.assertEqual(aggregate['combined']['days_active'], 1)
        self.assertEqual(aggregate['combined']['date_range'], {'start': '2026-10-16', 'end': '2026-10-16'})
        self.assertEqual(aggregate['combined']['session_summaries'][0]['date'], '2026-10-16')
        mismatch = self.aggregate(extra=['--timezone', 'UTC'])
        self.assertEqual(mismatch['combined']['total_sessions'], 0)
        self.assertEqual(mismatch['mismatched_timezone_metas_ignored'], 1)
        self.assertEqual(self.collect(extra=['--timezone', 'UTC'])['parsed_now'], 1)
        self.assertEqual(self.meta()['message_hours'], [23, 0])
        self.assertEqual(self.aggregate()['combined']['days_active'], 2)
        self.assertEqual(self.collect(extra=['--timezone', 'UTC'])['from_cache'], 1)

    def test_same_window_manifest_replacement_and_maxload_bind_collection(self):
        second_path = self.path.with_name(f'rollout-synthetic-{B}.jsonl')
        second_path.write_bytes(data([row('session_meta', {'id': B}, SINCE),
                                      user('second synthetic task', AS_OF)]))
        manifest = self.root / 'manifest.json'
        def freeze(paths, snapshot_id):
            manifest.write_text(json.dumps({'snapshot_id': snapshot_id, 'files': [{
                'path': str(path), 'session_id': A if path == self.path else B,
                'byte_length': path.stat().st_size, 'mtime_ns': path.stat().st_mtime_ns,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths]}))
        flags = ['--codex-snapshot-manifest', str(manifest)]
        freeze([self.path, second_path], 'synthetic-first')
        self.collect(extra=flags)
        self.assertEqual(self.aggregate()['combined']['total_sessions'], 2)
        freeze([second_path], 'synthetic-second')
        summary = self.collect(extra=flags)
        self.assertEqual(summary['included_meta_keys'], [['codex', B]])
        aggregate = self.aggregate()
        self.assertEqual(aggregate['combined']['total_sessions'], 1)
        self.assertEqual(aggregate['out_of_collection_metas_ignored'], 1)
        self.assertTrue((self.home / f'cache/meta/codex/{A}.json').exists())
        # Same-window stale entries are not revived when max-load prevents parsing.
        freeze([second_path], 'synthetic-third')
        summary = self.collect(extra=[*flags, '--max-load', '0'])
        self.assertEqual(summary['included_meta_keys'], [])
        self.assertEqual(summary['note_remaining_uncached'], 1)
        self.assertEqual(self.aggregate()['combined']['total_sessions'], 0)
        self.collect(extra=flags)
        summary = self.collect(extra=[*flags, '--max-load', '0'])
        self.assertEqual(summary['included_meta_keys'], [['codex', B]])
        self.assertEqual(summary['from_cache'], 1)
        self.assertEqual(self.aggregate()['combined']['total_sessions'], 1)

    @unittest.skipUnless(ZSTD, 'zstd executable unavailable')
    def test_archived_zstd_and_physical_frozen_prefix_hash(self):
        compressed = subprocess.run([ZSTD, '-q', '-c'], input=data(fixture_rows()),
                                    check=True, capture_output=True).stdout
        self.path.unlink()
        archived = self.codex / 'archived_sessions' / f'rollout-synthetic-{A}.jsonl.zst'
        archived.parent.mkdir(parents=True)
        archived.write_bytes(compressed)
        # A second zstd frame added after freezing must not leak into the read.
        appended = subprocess.run([ZSTD, '-q', '-c'], input=data([user('appended', AS_OF)]),
                                  check=True, capture_output=True).stdout
        archived.write_bytes(compressed + appended)
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps({'snapshot_id': 'synthetic-freeze', 'files': [{
            'path': str(archived), 'session_id': A, 'byte_length': len(compressed),
            'mtime_ns': 123, 'sha256': hashlib.sha256(compressed).hexdigest()}]}))
        self.assertEqual(codex_scan(self.codex)[0]['path'], str(archived))
        self.collect(extra=['--codex-snapshot-manifest', str(manifest)])
        self.assertEqual(self.meta()['user_message_count'], 1)
        self.assertEqual(self.meta()['source_snapshot_id'], 'synthetic-freeze')
        self.assertEqual(self.meta()['source_audit']['offset_encoding'], 'decompressed_jsonl')
        # Plain archived JSONL is discovered too, with no dependence on sessions/.
        archived.unlink()
        plain = archived.with_suffix('')
        plain.write_bytes(data(fixture_rows()))
        self.assertEqual(codex_scan(self.codex)[0]['path'], str(plain))


if __name__ == '__main__':
    unittest.main()
