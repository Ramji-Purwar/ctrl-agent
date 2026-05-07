# test_agent.py
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.agent_loop import run_agent
from core.memory import clear_history

clear_history()

tests = [
    "what is 2 + 2",
    f"make a folder called agent_test inside {ROOT}",
    f"list the contents of {ROOT}",
    f"find a file named settings.py in {ROOT}",
    f"read the file {ROOT / 'config' / 'settings.py'}",
]

for i, prompt in enumerate(tests):
    print(f"\n{'='*60}")
    print(f"TEST {i+1}: {prompt}")
    print('='*60)

    start = time.time()
    result = run_agent(prompt)
    elapsed = time.time() - start

    print(f"Agent  : {result['response']}")
    print(f"Tools  : {result.get('tools_used', [])}")
    print(f"Success: {result['success']}")
    print(f"Time   : {elapsed:.2f}s")