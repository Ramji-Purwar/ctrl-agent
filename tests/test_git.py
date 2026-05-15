import sys
import time
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.agent_loop import run_agent
from core.memory import clear_history

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s")

# ── Config ────────────────────────────────────────────────────────────────────
# Change this to a real repo name that exists inside your BASE_DIR.
# The repo must have at least one commit. Does NOT need to have a remote.
TEST_REPO = "ctrl-agent"

DELAY_SUCCESS = 15
DELAY_FAILURE = 25
MEMORY_RESET_INTERVAL = 4


# ── Test Runner ───────────────────────────────────────────────────────────────
def run_test(label: str, prompt: str):
    print(f"\n{'=' * 70}")
    print(f"TEST : {label}")
    print(f"USER : {prompt}")
    print('=' * 70)

    start = time.time()
    try:
        result = run_agent(prompt)
    except Exception as e:
        result = {"success": False, "response": str(e), "tools_used": []}

    elapsed = time.time() - start

    print(f"AGENT   : {result['response']}")
    print(f"TOOLS   : {result.get('tools_used', [])}")
    print(f"SUCCESS : {result['success']}")
    print(f"TIME    : {elapsed:.2f}s")

    if result["success"]:
        print(f"Waiting {DELAY_SUCCESS}s...")
        time.sleep(DELAY_SUCCESS)
    else:
        print(f"Failure — cooling down {DELAY_FAILURE}s...")
        time.sleep(DELAY_FAILURE)

    return result


# ── Tests ─────────────────────────────────────────────────────────────────────
def main():
    clear_history()

    tests = [

        # ── Status ────────────────────────────────────────────────────────
        (
            "Git status by name",
            f"what's the status of {TEST_REPO}?"
        ),
        (
            "Git status casual",
            f"any changes in {TEST_REPO}?"
        ),
        (
            "Git status clean check",
            f"is {TEST_REPO} clean or does it have uncommitted changes?"
        ),

        # ── Log ───────────────────────────────────────────────────────────
        (
            "Recent commits",
            f"show me the last few commits in {TEST_REPO}"
        ),
        (
            "Commit history with limit",
            f"show me the last 3 commits in {TEST_REPO}"
        ),
        (
            "Commit history casual",
            f"what have i been working on in {TEST_REPO} recently?"
        ),

        # ── Branches ──────────────────────────────────────────────────────
        (
            "List branches",
            f"what branches does {TEST_REPO} have?"
        ),
        (
            "Current branch",
            f"which branch am i on in {TEST_REPO}?"
        ),

        # ── Diff ──────────────────────────────────────────────────────────
        (
            "Unstaged diff",
            f"show me what i changed in {TEST_REPO}"
        ),
        (
            "Staged diff",
            f"show me what's staged in {TEST_REPO}"
        ),

        # ── Dry run push ──────────────────────────────────────────────────
        (
            "Dry run push",
            f"what would happen if i push {TEST_REPO}?"
        ),
        (
            "Dry run casual",
            f"is there anything to push in {TEST_REPO}?"
        ),

        # ── Push without confirmation — must ask first, not execute ───────
        (
            "Push no confirmation",
            f"push {TEST_REPO}"
        ),

        # ── Multi-step ────────────────────────────────────────────────────
        (
            "Status then log",
            f"check the status of {TEST_REPO} and show me the recent commits"
        ),
        (
            "Status then diff",
            f"what's changed and what's staged in {TEST_REPO}?"
        ),

        # ── Repo not found ────────────────────────────────────────────────
        (
            "Nonexistent repo",
            "what's the status of fakerepo999?"
        ),
        (
            "Vague repo name",
            "show me git status"
        ),

        # ── Conversational continuity ─────────────────────────────────────
        (
            "Follow-up branch question",
            "what branch was that again?"
        ),
        (
            "Follow-up last commit",
            "what was the last commit message?"
        ),

        # ── Confirm push after dry run ────────────────────────────────────
        # These two run back-to-back intentionally — second message confirms the first.
        # WARNING: this will actually push if your repo has a remote and commits to push.
        # Comment out if you don't want a real push to happen.
        (
            "Dry run before confirm",
            f"show me what would be pushed for {TEST_REPO}"
        ),
        (
            "Confirm push",
            "yes go ahead and push"
        ),

    ]

    results = []

    for i, (label, prompt) in enumerate(tests, start=1):
        if i % MEMORY_RESET_INTERVAL == 0:
            print("\nClearing conversation history...\n")
            clear_history()

        result = run_test(label, prompt)
        results.append((label, result["success"]))

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print('=' * 70)

    passed = 0
    for label, success in results:
        status = "PASS" if success else "FAIL"
        print(f"[{status}] {label}")
        if success:
            passed += 1

    print(f"\n{passed}/{len(results)} tests passed")


if __name__ == "__main__":
    main()