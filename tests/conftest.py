import os

# Settings are read at import time, so the environment must be populated before
# any module under test is imported.
os.environ.setdefault("GITLAB_SECRET", "test-secret")
os.environ.setdefault("GITLAB_TOKEN", "test-token")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
