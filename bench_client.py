import statistics
import subprocess
import time
import timeit

from libqtile.command.client import InteractiveCommandClient, IPCCommandInterface
from libqtile.ipc import PersistentClient, ReconnectingClient, find_sockfile
from libqtile.utils import guess_terminal


def get_window_id_from_pid(pid: int) -> int:
    result = subprocess.run(f"xdotool search --pid {pid}", shell=True, capture_output=True)
    return int(result.stdout.decode().strip())


def benchmark(fn, warmup=10, repeat=5, number=200):
    # warmup
    for _ in range(warmup):
        fn()

    times = timeit.repeat(fn, repeat=repeat, number=number)
    per_call = [t / number * 1000 for t in times]  # ms per call

    return {
        "min": min(per_call),
        "max": max(per_call),
        "mean": statistics.mean(per_call),
        "median": statistics.median(per_call),
    }


def setup_persistent():
    client = PersistentClient(find_sockfile())
    interface = IPCCommandInterface(client)
    return InteractiveCommandClient(interface)


def setup_reconnecting():
    client = ReconnectingClient(find_sockfile())
    interface = IPCCommandInterface(client)
    return InteractiveCommandClient(interface)


# Bench running a single command including creating the client
def bench_single_use_with_setup(setup):
    def single_use():
        client = setup()
        return client.commands()

    return benchmark(single_use, repeat=20, number=200)


# Bench running a single command with an existing client
def bench_single_use(setup):
    def single_use(client):
        return client.commands()

    client = setup()
    return benchmark(lambda: single_use(client), repeat=20, number=200)


def bench_multi_use(setup):
    def multi_use():
        client = setup()
        terminal = guess_terminal() or "xterm"
        window_count = len(client.windows())
        windows = list()
        num_wins = 10

        for _ in range(num_wins):
            pid = client.spawn(terminal)
            windows.append(pid)

        while True:
            if len(client.windows()) == window_count + num_wins:
                break

        for pid in windows:
            # this is probably most of the benchmarks time unfortunately
            id = get_window_id_from_pid(pid)
            window = client.window[id]
            window.kill()

    # Not very good statistics, but it should suffice for an informative
    # example
    return benchmark(multi_use, warmup=0, repeat=1, number=1)


def main():
    benches = [
        (
            "Single use with setup: Reconnecting",
            lambda: bench_single_use_with_setup(setup_reconnecting),
        ),
        (
            "Single use with setup: Persistent",
            lambda: bench_single_use_with_setup(setup_persistent),
        ),
        (
            "Single use with existing client: Reconnecting",
            lambda: bench_single_use(setup_reconnecting),
        ),
        (
            "Single use with existing client: Persistent",
            lambda: bench_single_use(setup_persistent),
        ),
        (
            "Multiple use: Reconnecting",
            lambda: bench_multi_use(setup_reconnecting),
        ),
        (
            "Multiple use: Persistent",
            lambda: bench_multi_use(setup_persistent),
        ),
    ]

    for description, bench in benches:
        print(f"Running: {description}")
        result = bench()
        print(
            "Min: {: >9.4f}ms Max: {: >9.4f}ms Mean: {: >9.4f}ms Median: {: >9.4f}ms".format(
                result["min"], result["max"], result["mean"], result["median"]
            )
        )
        time.sleep(0.2)


if __name__ == "__main__":
    main()
