"""python -m pulse.seed — regenerate the demo company for today."""

import json

from pulse.seed import build, seed_dir

if __name__ == "__main__":
    story = build()
    print(f"seed written to {seed_dir()}")
    print(json.dumps({k: v for k, v in story.items() if k != "quiet_since"}, ensure_ascii=False, indent=1))
