"""Tests for action_pusher.py: sequence numbers, batching and the three push outcomes."""

import json
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import action_builder as ab
from action_builder import ActionError
from action_pusher import push_parent_actions, resolve_parent_user_id
from database import Database, create_family, update_family_parent_user_id, reserve_sequence_numbers

TOKEN = 'T' * 32
OWN_DEVICE = 'dev001'
PARENT = 'par001'


class FakeClient:
    """Records push_actions calls; the answers are scripted."""

    def __init__(self, answers=None):
        self.calls = []
        self.answers = list(answers or [])

    def push_actions(self, device_auth_token, actions):
        self.calls.append((device_auth_token, actions))
        if self.answers:
            return self.answers.pop(0)
        return SimpleNamespace(success=True, data={'shouldDoFullSync': False}, error_message=None, status_code=200)


def ok(full_sync=False):
    return SimpleNamespace(success=True, data={'shouldDoFullSync': full_sync}, error_message=None, status_code=200)


@pytest.fixture
def db(tmp_path):
    database = Database(db_path=str(tmp_path / 'pusher.db'))
    database.init_db()
    create_family(
        db=database, device_auth_token=TOKEN, mail='a@b.c', parent_password_hash='h1',
        parent_password_second_hash='h2', parent_password_second_salt='s', parent_password_encrypted=False)
    update_family_parent_user_id(database, TOKEN, PARENT)
    yield database
    database.close()


def rule_actions(n):
    return [ab.delete_timelimit_rule(ab.new_id()) for _ in range(n)]


class TestSequenceNumbers:
    def test_start_at_zero_and_are_consecutive(self, db):
        assert reserve_sequence_numbers(db, TOKEN, 1) == 0
        assert reserve_sequence_numbers(db, TOKEN, 3) == 1
        assert reserve_sequence_numbers(db, TOKEN, 1) == 4

    def test_per_token(self, db):
        assert reserve_sequence_numbers(db, TOKEN, 2) == 0
        assert reserve_sequence_numbers(db, 'other-token', 1) == 0

    def test_count_must_be_positive(self, db):
        with pytest.raises(ValueError):
            reserve_sequence_numbers(db, TOKEN, 0)

    def test_numbers_are_consumed_even_when_the_push_fails(self, db):
        client = FakeClient([SimpleNamespace(success=False, data=None, error_message='boom', status_code=500)])
        push_parent_actions(client, TOKEN, OWN_DEVICE, rule_actions(2), db=db)
        client2 = FakeClient()
        push_parent_actions(client2, TOKEN, OWN_DEVICE, rule_actions(1), db=db)
        # the first two numbers (0, 1) are gone; the server rejects reuse silently
        assert client2.calls[0][1][0]['sequenceNumber'] == 2


class TestPush:
    def test_device_integrity_parent_items(self, db):
        client = FakeClient()
        actions = rule_actions(2)
        result = push_parent_actions(client, TOKEN, OWN_DEVICE, actions, db=db)
        assert result.request_ok and result.confirmed and result.sent == 2
        token, items = client.calls[0]
        assert token == TOKEN
        assert [i['sequenceNumber'] for i in items] == [0, 1]
        for item, action in zip(items, actions):
            assert item['type'] == 'parent' and item['integrity'] == 'device'
            assert item['userId'] == PARENT
            assert json.loads(item['encodedAction']) == action

    def test_password_integrity_when_second_hash_given(self, db):
        client = FakeClient()
        push_parent_actions(client, TOKEN, OWN_DEVICE, rule_actions(1), db=db, second_hash='$2a$12$k')
        assert client.calls[0][1][0]['integrity'].startswith('password:')

    def test_batches_of_at_most_25(self, db):
        client = FakeClient()
        result = push_parent_actions(client, TOKEN, OWN_DEVICE, rule_actions(60), db=db)
        assert [len(c[1]) for c in client.calls] == [25, 25, 10]
        assert result.sent == 60 and result.confirmed
        numbers = [i['sequenceNumber'] for c in client.calls for i in c[1]]
        assert numbers == list(range(60))

    def test_nothing_to_push(self, db):
        client = FakeClient()
        result = push_parent_actions(client, TOKEN, OWN_DEVICE, [], db=db)
        assert result.request_ok and result.confirmed and client.calls == []


class TestOutcomes:
    def test_server_does_not_confirm(self, db):
        """shouldDoFullSync=true with HTTP 200 means at least one action was skipped."""
        client = FakeClient([ok(full_sync=True)])
        result = push_parent_actions(client, TOKEN, OWN_DEVICE, rule_actions(1), db=db)
        assert result.request_ok is True
        assert result.confirmed is False and result.should_do_full_sync is True
        assert 'not' in result.summary

    def test_request_failure_stops_further_batches(self, db):
        client = FakeClient([ok(), SimpleNamespace(success=False, data=None, error_message='HTTP 401', status_code=401)])
        result = push_parent_actions(client, TOKEN, OWN_DEVICE, rule_actions(60), db=db)
        assert result.request_ok is False and result.confirmed is False
        assert len(client.calls) == 2 and result.sent == 25
        assert 'HTTP 401' in result.summary

    def test_unconfirmed_batch_is_remembered_across_batches(self, db):
        client = FakeClient([ok(full_sync=True), ok(), ok()])
        result = push_parent_actions(client, TOKEN, OWN_DEVICE, rule_actions(60), db=db)
        assert len(client.calls) == 3 and result.confirmed is False


class TestParentResolution:
    def test_malformed_action_sends_nothing_and_reserves_nothing(self, db):
        client = FakeClient()
        with pytest.raises(ActionError):
            # password integrity needs a valid own device id for the HMAC
            push_parent_actions(client, TOKEN, 'bad id', rule_actions(2), db=db, second_hash='$2a$12$k')
        assert client.calls == []
        assert reserve_sequence_numbers(db, TOKEN, 1) == 0

    def test_unknown_parent_raises(self, db):
        client = FakeClient()
        with pytest.raises(ActionError):
            push_parent_actions(client, 'unknown-token', OWN_DEVICE, rule_actions(1), db=db)
        assert client.calls == []

    def test_current_user_of_own_device_wins(self, db):
        with db._lock:
            conn = db.get_connection()
            conn.cursor().execute(
                'INSERT INTO devices (id, device_auth_token, name, model, created_at, current_user_id) '
                'VALUES (?, ?, ?, ?, ?, ?)', (OWN_DEVICE, TOKEN, 'n', 'm', '0', 'abc123'))
            conn.commit()
        assert resolve_parent_user_id(db, TOKEN, OWN_DEVICE) == 'abc123'
        assert resolve_parent_user_id(db, TOKEN, 'zzz999') == PARENT   # falls back to the family record
