from unittest.mock import Mock
import pytest
from app.services import cohort_worker as worker

def test_queue_uninitialized(monkeypatch):
    monkeypatch.setattr(worker,'_queue',None)
    with pytest.raises(RuntimeError,match='not initialised'):
        worker.get_queue()

def test_queue_returns_initialized_instance(monkeypatch):
    queue=Mock()
    monkeypatch.setattr(worker,'_queue',queue)
    assert worker.get_queue() is queue

def test_start_workers_initializes_queue_and_threads(monkeypatch,tmp_path):
    queue=Mock()
    constructor=Mock(return_value=queue)
    thread_factory=Mock()
    monkeypatch.setattr(worker.persistqueue,'SQLiteAckQueue',constructor)
    monkeypatch.setattr(worker.threading,'Thread',thread_factory)
    monkeypatch.setattr(worker.settings,'queue_data_path',str(tmp_path/'queue'))
    monkeypatch.setattr(worker.settings,'worker_count',3)
    worker.start_workers()
    assert worker.get_queue() is queue
    assert (tmp_path/'queue').is_dir()
    assert thread_factory.call_count==3
    assert len(worker._worker_threads)==3
    for call in thread_factory.return_value.start.call_args_list:
        assert call.args==()

def test_stop_workers_signals_and_joins(monkeypatch):
    event=Mock()
    threads=[Mock(),Mock()]
    for thread in threads: thread.is_alive.return_value=False
    monkeypatch.setattr(worker,'_stop_event',event)
    monkeypatch.setattr(worker,'_worker_threads',threads)
    worker.stop_workers()
    event.set.assert_called_once()
    for thread in threads: thread.join.assert_called_once_with(timeout=60)
