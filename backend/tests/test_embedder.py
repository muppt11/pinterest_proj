"""Model-source selection (the model itself isn't loaded in unit tests)."""

from pathlib import Path

from app.services.embedder import HUB_MODEL, WEIGHTS_FILE, model_name


def test_prefers_verified_local_copy(tmp_path: Path) -> None:
    (tmp_path / WEIGHTS_FILE).write_bytes(b"")
    assert model_name(tmp_path) == f"local-dir:{tmp_path}"


def test_falls_back_to_hub_without_local_weights(tmp_path: Path) -> None:
    assert model_name(tmp_path) == HUB_MODEL
    assert model_name(None) == HUB_MODEL



def test_worker_exits_when_its_parent_dies() -> None:
    """Regression: dev-server reloads used to leave orphaned model workers running.

    A child process starts a watched grandchild, reports its PID, then dies abruptly (like a
    killed reload). The grandchild must notice and exit on its own.
    """
    import multiprocessing
    import os
    import time

    ctx = multiprocessing.get_context("spawn")
    receiver, sender = ctx.Pipe(duplex=False)
    child = ctx.Process(target=_spawn_and_report, args=(sender,))
    child.start()
    assert receiver.poll(30), "child never reported the grandchild PID"
    grandchild_pid = receiver.recv()
    child.join(timeout=30)

    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            os.kill(grandchild_pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.2)
    os.kill(grandchild_pid, 9)
    raise AssertionError("orphaned worker kept running")


def _watched(parent_pid: int) -> None:
    import time

    from app.services.embedder import _exit_when_orphaned

    _exit_when_orphaned(parent_pid, interval_s=0.2)
    time.sleep(30)


def _spawn_and_report(sender) -> None:  # type: ignore[no-untyped-def]
    import multiprocessing
    import os

    grandchild = multiprocessing.get_context("spawn").Process(target=_watched, args=(os.getpid(),))
    grandchild.start()
    sender.send(grandchild.pid)  # Pipe.send is synchronous, unlike Queue.put
    os._exit(0)  # die abruptly, like a killed reload process
