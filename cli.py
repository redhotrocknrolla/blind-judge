#!/usr/bin/env python3
"""
Blind Judge CLI
  blind-judge serve              — запустить сервер
  blind-judge audit input.json  — прогнать файл локально
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import load_config
from judge import audit


def cmd_serve(args):
    import uvicorn
    cfg = load_config()
    host = args.host or cfg["server"]["host"]
    port = args.port or cfg["server"]["port"]
    print(f"[blind-judge] Starting server on {host}:{port}")
    uvicorn.run("api:app", host=host, port=port, reload=False, app_dir="src")


def cmd_audit(args):
    cfg = load_config()
    with open(args.input, encoding="utf-8") as f:
        input_data = json.load(f)
    result = audit(input_data, cfg)
    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent))


def main():
    parser = argparse.ArgumentParser(prog="blind-judge")
    sub = parser.add_subparsers(dest="command")

    # serve
    serve_p = sub.add_parser("serve", help="Запустить HTTP сервер")
    serve_p.add_argument("--host", default=None)
    serve_p.add_argument("--port", type=int, default=None)

    # audit
    audit_p = sub.add_parser("audit", help="Прогнать input.json локально")
    audit_p.add_argument("input", help="Путь к input.json")
    audit_p.add_argument("--pretty", action="store_true")

    args = parser.parse_args()

    if args.command == "serve":
        cmd_serve(args)
    elif args.command == "audit":
        cmd_audit(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
