"""Run the task4_v2 feedback service (FeedbackServiceV2 with Task 2's v2 components through Task 3's tpo_v2).

    source ~/.dashscope_env      # DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL; never printed or written
    PYTHONDONTWRITEBYTECODE=1 python serve_v2.py --data store_v2/ --port 8005

One process, one engine thread, as serve.py."""
import argparse
import os
import sys

sys.dont_write_bytecode = True

import uvicorn  # noqa: E402

from feedback_service.app import create_app  # noqa: E402
from feedback_service.service import DEFAULT_CONFIG  # noqa: E402
from feedback_service_v2.checks import startup_checks  # noqa: E402
from feedback_service_v2.service import build_service_v2  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="storage directory (created if missing)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8005)
    ap.add_argument("--default-config", default=DEFAULT_CONFIG)
    args = ap.parse_args()
    missing = [v for v in ("DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL") if not os.environ.get(v)]
    if missing:
        sys.exit(f"refused: {', '.join(missing)} not set (source ~/.dashscope_env in this command)")
    check = startup_checks()
    if not check["ok"]:
        sys.exit(f"refused: Task 3 files differ from its protocols: {check['task3_v1']['changed']} "
                 f"{check['task3_v2']['changed']}")
    service = build_service_v2(args.data, default_config=args.default_config,
                               startup_checks={"task3_protocol_hashes_match": True,
                                               "task3_v2_protocol_hashes_match": True,
                                               "task3_files_checked": check["task3_v1"]["files"] +
                                               check["task3_v2"]["files"]})
    uvicorn.run(create_app(service), host=args.host, port=args.port, workers=1, log_level="warning",
                access_log=False)


if __name__ == "__main__":
    main()
