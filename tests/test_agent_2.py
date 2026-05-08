import sys
import time
import shutil
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.agent_loop import run_agent
from core.memory import clear_history

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s")

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(r"C:\Users\r4849")
SANDBOX = BASE_DIR / "agent_test_sandbox"

# safer delays for rate limits
DELAY_SUCCESS = 15
DELAY_FAILURE = 25

# clear chat memory every N tests
MEMORY_RESET_INTERVAL = 5


# ── Setup ─────────────────────────────────────────────────────────────────────
def setup():
    print("Setting up sandbox...")

    SANDBOX.mkdir(parents=True, exist_ok=True)

    # Project folders
    (SANDBOX / "projects" / "my-website").mkdir(parents=True, exist_ok=True)
    (SANDBOX / "projects" / "ml-homework").mkdir(parents=True, exist_ok=True)

    # Misc folders
    (SANDBOX / "notes").mkdir(exist_ok=True)
    (SANDBOX / "downloads").mkdir(exist_ok=True)

    # Website project
    (SANDBOX / "projects" / "my-website" / "index.html").write_text(
        "<html><body><h1>My Website</h1></body></html>",
        encoding="utf-8"
    )

    (SANDBOX / "projects" / "my-website" / "style.css").write_text(
        "body { margin: 0; font-family: sans-serif; }",
        encoding="utf-8"
    )

    # ML homework project
    (SANDBOX / "projects" / "ml-homework" / "train.py").write_text(
        "import numpy as np\n\nX = np.array([1, 2, 3])\nprint(X)\n",
        encoding="utf-8"
    )

    (SANDBOX / "projects" / "ml-homework" / "notes.txt").write_text(
        "Lecture 4: linear regression\nDeadline: Friday\nTODO: normalize features",
        encoding="utf-8"
    )

    # Notes
    (SANDBOX / "notes" / "todo.txt").write_text(
        "1. Submit assignment\n2. Read chapter 5\n3. Call mom",
        encoding="utf-8"
    )

    (SANDBOX / "notes" / "ideas.md").write_text(
        "# Project Ideas\n- Build a CLI agent\n- Make a portfolio site\n",
        encoding="utf-8"
    )

    # Downloads
    (SANDBOX / "downloads" / "resume.pdf").write_text(
        "[fake pdf content — resume v3]",
        encoding="utf-8"
    )

    print(f"Sandbox ready at: {SANDBOX}\n")


# ── Cleanup ───────────────────────────────────────────────────────────────────
def teardown():
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
        print(f"\nSandbox deleted: {SANDBOX}")


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
        result = {
            "success": False,
            "response": str(e),
            "tools_used": [],
        }

    elapsed = time.time() - start

    print(f"AGENT   : {result['response']}")
    print(f"TOOLS   : {result.get('tools_used', [])}")
    print(f"SUCCESS : {result['success']}")
    print(f"TIME    : {elapsed:.2f}s")

    # ── Delay handling ────────────────────────────────────────────
    if result["success"]:
        print(f"Waiting {DELAY_SUCCESS}s to avoid rate limits...")
        time.sleep(DELAY_SUCCESS)

    else:
        print(f"Failure detected — cooling down for {DELAY_FAILURE}s...")
        time.sleep(DELAY_FAILURE)

    return result


# ── Tests ─────────────────────────────────────────────────────────────────────
def main():
    setup()

    clear_history()

    tests = [

        # ── Basic conversation ─────────────────────────────────────────────
        (
            "General python question",
            "quick one — whats the difference between a list and tuple in python?"
        ),

        (
            "Coding workflow question",
            "why do people use virtual environments in python?"
        ),

        # ── Folder listing ─────────────────────────────────────────────────
        (
            "Check sandbox",
            "can you check whats in the agent_test_sandbox folder?"
        ),

        (
            "Projects folder",
            "what projects do i have in the projects folder?"
        ),

        (
            "Notes folder",
            "lemme know whats inside the notes folder"
        ),

        # ── File search ────────────────────────────────────────────────────
        (
            "Find train.py",
            "where did i put train.py?"
        ),

        (
            "Partial filename search",
            "theres some css file with sty in the name somewhere"
        ),

        (
            "Search by topic",
            "search for anything related to regression"
        ),

        (
            "Typo search",
            "can u find trian.py"
        ),

        # ── Read files ─────────────────────────────────────────────────────
        (
            "Open todo file",
            "open the todo file in notes"
        ),

        (
            "Read train.py",
            "show me whats inside train.py from the ml-homework project"
        ),

        (
            "Read ideas.md",
            "what ideas do i have written in ideas.md"
        ),

        (
            "Open resume",
            "open the resume in downloads"
        ),

        # ── Multi-step tasks ──────────────────────────────────────────────
        (
            "Find and open notes",
            "find notes.txt somewhere and show me whats in it"
        ),

        (
            "Homework files",
            "find the homework project and tell me what files are there"
        ),

        (
            "Find css and open",
            "find the css file in my website project and open it"
        ),

        # ── Create folders ────────────────────────────────────────────────
        (
            "Create assignments folder",
            "make a folder called assignments"
        ),

        (
            "Verify assignments folder",
            "can you check if the assignments folder is there now?"
        ),

        (
            "Create temp folder",
            "make a temp folder"
        ),

        (
            "Nested folder creation",
            "make a folder called week1 inside assignments"
        ),

        # ── Conversational continuity ─────────────────────────────────────
        (
            "Remember previous todo",
            "what was in that todo file again?"
        ),

        (
            "Follow-up notes reference",
            "open that regression notes file"
        ),

        (
            "Contextual follow-up",
            "what other files were in that same folder?"
        ),

        # ── Failure handling ──────────────────────────────────────────────
        (
            "Missing file",
            "look for fakefile123.py"
        ),

        (
            "Read missing file",
            "open doesnotexist.txt from notes"
        ),

        (
            "Impossible path",
            "open abc/xyz/random.txt"
        ),

        # ── Ambiguous prompts ─────────────────────────────────────────────
        (
            "Open notes file",
            "open the notes file"
        ),

        (
            "Folder memory",
            "what folder am i working with again?"
        ),

        (
            "Very casual phrasing",
            "yo can you check that homework thing"
        ),
    ]

    results = []

    # ── Execute tests ─────────────────────────────────────────────────────
    for i, (label, prompt) in enumerate(tests, start=1):

        # periodically clear memory to reduce token buildup
        if i % MEMORY_RESET_INTERVAL == 0:
            print("\nClearing conversation history...\n")
            clear_history()

        result = run_test(label, prompt)

        results.append((label, result["success"]))

    # ── Summary ────────────────────────────────────────────────────────────
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

    teardown()


if __name__ == "__main__":
    main()