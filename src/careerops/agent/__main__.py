import argparse
import asyncio
import getpass
import json
import os
import sys
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ValidationError

from careerops.agent.client import login
from careerops.agent.contracts import AgentConfig, AgentError, RecordQuery
from careerops.agent.gateway import ProjectAgent
from careerops.agent.storage import ProtectedStore
from careerops.domain.project_records import CheckpointInput, ProjectInput


def config_from_environment() -> AgentConfig:
    directory = os.environ.get("CAREEROPS_AGENT_STATE_DIR")
    if directory is None:
        base = os.environ.get("LOCALAPPDATA")
        if base is None:
            raise AgentError(
                "STATE_DIRECTORY_REQUIRED",
                "Set CAREEROPS_AGENT_STATE_DIR to your private state directory.",
            )
        directory = str(Path(base) / "CareerOps" / "agent")
    return AgentConfig(
        api_url=os.environ.get("CAREEROPS_AGENT_API_URL", "http://127.0.0.1:8000"),
        state_dir=Path(directory),
    )


def read_packet(path: Path) -> CheckpointInput:
    with path.open("rb") as stream:
        raw = stream.read(131073)
    if len(raw) > 131072:
        raise AgentError("PACKET_TOO_LARGE", "Selected packet file exceeds 128 KiB.")
    return CheckpointInput.model_validate_json(raw)


async def execute(args: argparse.Namespace) -> int:
    config = config_from_environment()
    store = ProtectedStore(config.state_dir)
    if args.command == "login":
        if not sys.stdin.isatty():
            raise AgentError(
                "INTERACTIVE_LOGIN_REQUIRED", "Sign in from your own interactive terminal."
            )
        credentials = await login(
            config, input("CareerOps email: ").strip(), getpass.getpass("Password: ")
        )
        store.save_credentials(credentials)
        print(
            "Local session protected. No token was printed. Re-login when the API session expires."
        )
        return 0
    agent = ProjectAgent(config, store)
    result: BaseModel
    if args.command == "projects":
        result = await agent.list_projects(RecordQuery(cursor=args.cursor, limit=args.limit))
    elif args.command == "register":
        result = await agent.register_project(
            ProjectInput(name=args.name, goal=args.goal), args.key
        )
    elif args.command == "submit":
        result = await agent.save_checkpoint(
            args.project, read_packet(args.packet), args.key, approved_for_upload=True
        )
    elif args.command == "pending":
        result = agent.list_pending_checkpoints()
    elif args.command == "replay":
        result = await agent.replay_checkpoint(args.packet_id)
    elif args.command == "context":
        result = await agent.get_project_context(args.project)
    elif args.command == "search":
        result = await agent.search_project_evidence(
            args.project, RecordQuery(query=args.query, cursor=args.cursor, limit=args.limit)
        )
    else:
        result = await agent.get_evidence(args.project, args.record)
    print(result.model_dump_json(indent=2))
    state = getattr(result, "state", "accepted")
    return 0 if state == "accepted" else 2


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CareerOps local project evidence client (Windows)."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "login", help="Sign in in this terminal; protect the session with Windows DPAPI."
    )
    projects = commands.add_parser("projects")
    projects.add_argument("--cursor")
    projects.add_argument("--limit", type=int, default=20)
    register = commands.add_parser("register")
    register.add_argument("--name", required=True)
    register.add_argument("--goal", required=True)
    register.add_argument("--key", type=UUID, required=True)
    submit = commands.add_parser(
        "submit", help="Upload only the explicitly selected checkpoint JSON file."
    )
    submit.add_argument("--project", type=UUID, required=True)
    submit.add_argument("--key", type=UUID, required=True)
    submit.add_argument("--packet", type=Path, required=True)
    commands.add_parser("pending")
    replay = commands.add_parser("replay")
    replay.add_argument("packet_id", type=UUID)
    for name in ("context", "search", "get"):
        command = commands.add_parser(name)
        command.add_argument("--project", type=UUID, required=True)
        if name == "search":
            command.add_argument("--query")
            command.add_argument("--cursor")
            command.add_argument("--limit", type=int, default=20)
        elif name == "get":
            command.add_argument("--record", type=UUID, required=True)
    args = parser.parse_args()
    try:
        code = asyncio.run(execute(args))
    except AgentError as exc:
        print(json.dumps({"code": exc.code, "message": exc.message}), file=sys.stderr)
        code = 2
    except (ValidationError, OSError, EOFError, KeyboardInterrupt):
        print(
            json.dumps(
                {
                    "code": "LOCAL_INPUT_ERROR",
                    "message": (
                        "Check local configuration and the selected packet; "
                        "no secret details are printed."
                    ),
                }
            ),
            file=sys.stderr,
        )
        code = 2
    raise SystemExit(code)


if __name__ == "__main__":
    main()
