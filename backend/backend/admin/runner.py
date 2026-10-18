"""``python -m backend.admin.runner``: the task runner service's entry point."""

import sys

from backend.admin.tasks.runner.main import main

if __name__ == "__main__":
    sys.exit(main())
