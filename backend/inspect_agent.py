import os

session_file = os.path.join(
    ".venv", "Lib", "site-packages", "livekit", "agents", "voice", "agent_session.py"
)
if os.path.exists(session_file):
    with open(session_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for idx, line in enumerate(lines):
            if "user_input_transcribed" in line:
                start = max(0, idx - 3)
                end = min(len(lines), idx + 8)
                print(f"Lines {start + 1} to {end}:")
                for j in range(start, end):
                    print(f"{j + 1}: {lines[j].strip()}")
                print("-" * 40)
