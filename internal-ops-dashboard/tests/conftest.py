import os

# Point tests at an in-memory-style file DB and temp log dir
# These must be set BEFORE any backend module is imported
os.environ["DB_PATH"] = "test_ops_dashboard.db"
os.environ["LOG_DIR"] = "/tmp/ops-test-logs"
os.environ["SIMULATE_LATENCY"] = "false"
os.environ["SIMULATE_FAILURES"] = "false"