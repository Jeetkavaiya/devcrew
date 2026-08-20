import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Make src/ importable the same way the project does locally/in Docker.
SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

EVAL_TASKS = [
    "Write a function that returns the maximum of two numbers.",
    "Write a function that checks if a given integer is prime.",
    "Write a function that reverses a string without using slicing or a built-in reverse.",
    "Write a function that returns the nth Fibonacci number using iteration.",
    "Write a function that removes duplicate elements from a list while preserving order.",
    "Write a function that checks whether a string is a palindrome, ignoring case and spaces.",
    "Write a function that returns the factorial of a non-negative integer.",
    "Write a function that merges two sorted lists into a single sorted list.",
    "Write a function that counts the frequency of each word in a given string.",
    "Write a function that finds the second largest number in a list of integers.",
    "Write a function that flattens a nested list of arbitrary depth.",
    "Write a function that checks if two strings are anagrams of each other.",
    "Write a function that implements binary search on a sorted list.",
    "Write a function that returns all pairs of numbers in a list that sum to a given target.",
    "Write a function that converts a Roman numeral string to an integer.",
]

assert len(EVAL_TASKS) == 15, "Eval set must contain exactly 15 tasks"


def parse_args():
    parser = argparse.ArgumentParser(description="DevCrew 15-task eval harness")
    parser.add_argument("--limit", type=int, default=None,
                         help="Only run the first N tasks (smoke test before burning full quota)")
    parser.add_argument("--model", type=str, default=None,
                         help="Override DEVCREW_MODEL for this run only")
    parser.add_argument("--output", type=str, default=None,
                         help="Path to write JSON results (default: eval_results/eval_<timestamp>.json). "
                              "Also the file --resume reads from.")
    parser.add_argument("--delay", type=float, default=20.0,
                         help="Seconds to pause between tasks to let the TPM window recover "
                              "(default: 20s). Set to 0 to disable.")
    parser.add_argument("--resume", action="store_true",
                         help="Skip tasks already completed (no error) in --output's file, if it exists")
    parser.add_argument("--max-tpm-retries", type=int, default=4,
                         help="How many times to retry a single task on a TPM burst limit before "
                              "giving up on that task and moving on (default: 4)")
    return parser.parse_args()


def extract_test_status(test_results) -> str:
    """Mirror the Reviewer's own backstop check: look for 'status: passed' in test_results."""
    text = str(test_results or "").lower()
    if "status: passed" in text:
        return "passed"
    if "status: failed" in text:
        return "failed"
    return "unknown"


def _write_results(output_path: Path, results: list, partial: bool) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "partial": partial,
        "task_count": len(results),
        "results": results,
    }
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2)


def _load_existing_results(output_path: Path) -> list:
    if not output_path.exists():
        return []
    try:
        with open(output_path) as f:
            payload = json.load(f)
        return payload.get("results", [])
    except (json.JSONDecodeError, OSError):
        return []


def run_eval(tasks: list, output_path: Path, delay: float = 20.0,
             resume: bool = False, max_tpm_retries: int = 4) -> list:
    from devcrew.api import _initial_state
    from devcrew.graph import build_graph

    graph = build_graph()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    results = _load_existing_results(output_path) if resume else []
    already_done = {r["index"] for r in results if r.get("error") is None}
    if already_done:
        print(f"Resuming: {len(already_done)} task(s) already completed in {output_path}, skipping them.\n")

    i = 1
    while i <= len(tasks):
        if i in already_done:
            i += 1
            continue

        task = tasks[i - 1]
        print(f"[{i}/{len(tasks)}] {task}")
        started = time.time()
        record = {"index": i, "task": task}
        tpm_retry_count = 0

        try:
            state = _initial_state(task)
            final_state = graph.invoke(state)
            elapsed = round(time.time() - started, 1)

            record.update({
                "approved": final_state.get("approved"),
                "iteration_count": final_state.get("iteration_count"),
                "test_status": extract_test_status(final_state.get("test_results")),
                "elapsed_seconds": elapsed,
                "error": None,
                "test_results": final_state.get("test_results"),
                "review_feedback": final_state.get("review_feedback"),
            })
            status_label = "PASS" if record["approved"] else "FAIL"
            print(f"    -> {status_label} in {record['iteration_count']} iteration(s), {elapsed}s")

            results.append(record)
            _write_results(output_path, results, partial=False)

            if delay:
                time.sleep(delay)

            i += 1

        except Exception as exc:  # noqa: BLE001 - harness must record any failure and decide whether to continue
            elapsed = round(time.time() - started, 1)
            exc_text = str(exc).lower()
            is_rate_limit = "rate" in exc_text and "limit" in exc_text
            is_tpm = is_rate_limit and "tokens per minute" in exc_text
            is_tpd = is_rate_limit and "tokens per day" in exc_text

            if is_tpm and not is_tpd and tpm_retry_count < max_tpm_retries:
                # Per-minute burst cap, not daily quota exhaustion -- back off and retry the
                # same task rather than aborting the run or skipping ahead. Capped so a task
                # that keeps re-triggering TPM (e.g. a long reviewer loop) can't spin forever.
                tpm_retry_count += 1
                wait_seconds = _parse_retry_after(str(exc)) or 20
                print(f"    -> TPM burst limit hit (retry {tpm_retry_count}/{max_tpm_retries}), "
                      f"waiting {wait_seconds:.1f}s...")
                time.sleep(wait_seconds)
                continue  # retry this same task, i unchanged

            if is_tpm and not is_tpd:
                print(f"    -> TPM limit hit {max_tpm_retries} times on this task, giving up on it "
                      f"and moving to the next one.")

            record.update({
                "approved": None,
                "iteration_count": None,
                "test_status": "error",
                "elapsed_seconds": elapsed,
                "error": f"{type(exc).__name__}: {exc}",
            })
            print(f"    -> ERROR: {type(exc).__name__}: {exc}")

            results.append(record)
            _write_results(output_path, results, partial=True)

            if is_tpd:
                print("\nDaily quota exhausted (TPD limit). Stopping early -- partial results saved.")
                print(f"Completed {len(results)}/{len(tasks)} tasks before stopping.")
                break
            # Non-quota error on a single task: log it and move on to the next task.
            i += 1

    return results


def _parse_retry_after(exc_text: str):
    """Pull a 'try again in Xs' / 'in Xms' hint out of a Groq error message, if present."""
    import re

    match = re.search(r"try again in ([\d.]+)(ms|s)", exc_text, re.IGNORECASE)
    if not match:
        return None
    value, unit = match.groups()
    seconds = float(value) / 1000 if unit.lower() == "ms" else float(value)
    return max(seconds, 1.0) + 1.0  # pad by 1s so we don't retry right on the edge


def print_summary(results: list) -> None:
    completed = [r for r in results if r["error"] is None]
    errored = [r for r in results if r["error"] is not None]
    passed = [r for r in completed if r["approved"]]

    print("\n" + "=" * 60)
    print("EVAL SUMMARY")
    print("=" * 60)
    print(f"Total tasks run:      {len(results)}")
    print(f"Completed (no error): {len(completed)}")
    print(f"Errored:              {len(errored)}")
    if completed:
        pass_rate = 100 * len(passed) / len(completed)
        iter_counts = [r["iteration_count"] for r in completed if r["iteration_count"] is not None]
        avg_iter = sum(iter_counts) / len(iter_counts) if iter_counts else 0.0
        print(f"Pass rate:            {len(passed)}/{len(completed)} ({pass_rate:.1f}%)")
        print(f"Avg iterations:       {avg_iter:.2f}")
    if errored:
        print("\nTasks with errors:")
        for r in errored:
            print(f"  [{r['index']}] {r['task'][:60]}... -> {r['error']}")
    print("=" * 60)


def main():
    args = parse_args()

    if args.model:
        os.environ["DEVCREW_MODEL"] = args.model
        print(f"Overriding DEVCREW_MODEL={args.model} for this run")

    tasks = EVAL_TASKS[: args.limit] if args.limit else EVAL_TASKS

    if args.output:
        output_path = Path(args.output)
    elif args.resume:
        # --resume with no --output: reuse the most recent eval_results file so there's
        # something sensible to resume from.
        candidates = sorted(Path("eval_results").glob("eval_*.json")) if Path("eval_results").exists() else []
        output_path = candidates[-1] if candidates else Path("eval_results") / "eval_resumed.json"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path("eval_results") / f"eval_{timestamp}.json"

    print(f"Running {len(tasks)} task(s) against model={os.environ.get('DEVCREW_MODEL', '(default)')}")
    print(f"Results will be written to {output_path}\n")

    results = run_eval(tasks, output_path, delay=args.delay,
                        resume=args.resume, max_tpm_retries=args.max_tpm_retries)
    print_summary(results)
    print(f"\nFull results saved to {output_path}")


if __name__ == "__main__":
    main()