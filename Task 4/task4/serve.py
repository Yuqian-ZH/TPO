"""Run the feedback service with the real components (Task 2 localization / attribution, Task 3 probe and TPO
loop, qwen3.8-max, Gurobi).

    source ~/.dashscope_env      # DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL; never printed or written
    PYTHONDONTWRITEBYTECODE=1 python serve.py --data store/ --port 8004

One process, one engine thread (plan 3.1): never run it with several uvicorn workers."""
import argparse
import os
import sys

sys.dont_write_bytecode = True

import uvicorn  # noqa: E402

from feedback_service.app import create_app  # noqa: E402
from feedback_service.bridge import task3_protocol_check  # noqa: E402
from feedback_service.service import DEFAULT_CONFIG, build_service  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="storage directory (created if missing)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8004)
    ap.add_argument("--default-config", default=DEFAULT_CONFIG)
    args = ap.parse_args()
    missing = [v for v in ("DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL") if not os.environ.get(v)]
    if missing:
        sys.exit(f"refused: {', '.join(missing)} not set (source ~/.dashscope_env in this command)")
    check = task3_protocol_check()
    if not check["ok"]:
        sys.exit(f"refused: Task 3 files differ from Task 3's protocol.json: {check['changed']}")
    service = build_service(args.data, default_config=args.default_config,
                            startup_checks={"task3_protocol_hashes_match": True, "task3_files_checked": check["files"]})
    uvicorn.run(create_app(service), host=args.host, port=args.port, workers=1, log_level="warning",
                access_log=False)


if __name__ == "__main__":
    main()
