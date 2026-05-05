# test_agent.py
import time
from core.agent_loop import run_agent
from core.memory import clear_history

clear_history()

tests = [
    "what is 2 + 2",
    "make a folder called agent_test inside C:\\Users\\r4849\\Desktop\\ctrl-agent",
    "list the contents of C:\\Users\\r4849\\Desktop\\ctrl-agent",
    "find a file named settings.py in C:\\Users\\r4849\\Desktop\\ctrl-agent",
    "read the file C:\\Users\\r4849\\Desktop\\ctrl-agent\\config\\settings.py",
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