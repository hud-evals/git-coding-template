import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import click
from mcp.server.fastmcp import FastMCP
from pydantic import Field

import hud_controller.problems
from hud_controller.utils import import_submodules

from .setup import git_setup, start_dinit
from .spec import PROBLEM_REGISTRY, Grade, ProblemSpec
from .tools.base import ToolResult

logger = logging.getLogger(__name__)
ONLY_SERVER = False

# NEW: workspace reuse controls (consumed by graders.AgentPatchGrader via import)
WORKSPACE_DIR: str | None = None
REUSE_WORKSPACE: bool = False
EXTRA_LOGGING: bool = False



def _truthy(s: str | None) -> bool:
    return str(s or "").strip().lower() in {"1", "true", "yes", "on"}


def configure_logging(enable_extra: bool = False) -> None:
    os.environ["HOME"] = "/home/ubuntu"
    """Configure colorized logging for CLI runs."""
    level = logging.DEBUG if enable_extra else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    # Remove existing handlers to avoid duplicate logs
    for h in list(root.handlers):
        root.removeHandler(h)

    class ColorFormatter(logging.Formatter):
        COLORS = {
            logging.DEBUG: "\033[90m",  # bright black / gray
            logging.INFO: "\033[36m",  # cyan
            logging.WARNING: "\033[33m",  # yellow
            logging.ERROR: "\033[31m",  # red
            logging.CRITICAL: "\033[95m",  # magenta
        }
        RESET = "\033[0m"

        def format(self, record: logging.LogRecord) -> str:
            msg = super().format(record)
            if enable_extra:
                color = self.COLORS.get(record.levelno, "")
                if color:
                    return f"{color}{msg}{self.RESET}"
            return msg

    # Set up StreamHandler for stderr output (with colors)
    stream_handler = logging.StreamHandler()
    fmt = "%(asctime)s %(levelname)-7s %(message)s"
    stream_handler.setFormatter(ColorFormatter(fmt))
    root.addHandler(stream_handler)

    # Set up FileHandler for file logging (without colors)
    log_dir = Path("/tmp/log")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    try:
        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        # Use plain formatter for file (no color codes)
        file_formatter = logging.Formatter(fmt)
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(level)
        root.addHandler(file_handler)

        # Log that we've set up file logging
        logger.info(f"Logging to file: {log_file}")
    except Exception as e:
        # If we can't create the file handler, just log to stderr
        logger.warning(f"Could not create file handler for {log_file}: {e}")

    # log some preliminary information about the environment
    logger.info("=== ENVIRONMENT DEBUG ===")
    logger.info(f"Environment variables: {os.environ}")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    logger.info(f"UID: {os.getuid()}")
    logger.info(f"GID: {os.getgid()}")
    logger.info(f"Home directory: {os.path.expanduser('~')}")


mcp = FastMCP("hudevals", port=8039, log_level="DEBUG", debug=True)

TEST_MODE = os.environ.get("MCP_TESTING_MODE", "1") in ["1", "true"]

if TEST_MODE:
    from .tools.bash import BashTool
    from .tools.edit import Command, EditTool

    edit_tool = EditTool()
    bash_tool = BashTool()

    @mcp.tool(
        name="str_replace_editor",
        description="Create and edit files using str_replace_editor.  Please use absolute paths for all file names.",
    )
    async def str_replace_editor(
        *,
        command: Command,
        path: str,
        file_text: str | None = None,
        view_range: list[int] | None = None,
        old_str: str | None = None,
        new_str: str | None = None,
        insert_line: int | None = None,
    ) -> ToolResult:
        """Edit or create files using string replacement operations.

        Args:
            command (Command): The edit command to perform (e.g., create, edit, view)
            path (str): Absolute path to the target file
            file_text (str | None, optional): Content to write when creating a new file. Defaults to None.
            view_range (list[int] | None, optional): Line range to view [start, end]. Defaults to None.
            old_str (str | None, optional): String to replace when editing. Defaults to None.
            new_str (str | None, optional): Replacement string when editing. Defaults to None.
            insert_line (int | None, optional): Line number for insertion. Defaults to None.

        Returns:
            ToolResult: Result of the edit operation
        """
        return await edit_tool(
            command=command,
            path=path,
            file_text=file_text,
            view_range=view_range,
            old_str=old_str,
            new_str=new_str,
            insert_line=insert_line,
        )

    @mcp.tool(
        name="bash",
        description="Run bash commands. If you need to restart the bash session, set restart to true.",
    )
    async def bash(*, command: str, restart: bool = False) -> ToolResult:
        return await bash_tool(
            command=command,
            restart=restart,
        )


# import all submodules
# we need to import all submodules of hud_controller.problems to ensure that the problems are registered
import_submodules(hud_controller.problems)


template = """
Use the tools provided to complete the following task:
The code is located in /home/ubuntu/ClickHouse

IMPORTANT: You do NOT have access to interactive editors (like vi, nano, or interactive git rebase).
For git operations that require editing:
- Use the str_replace_editor tool to edit files directly
- For git interactive rebase, use GIT_SEQUENCE_EDITOR to automate the editor
- Or use non-interactive git approaches when possible

<STATEMENT>
"""


# helper to lookup a problem spec by id
def _get_spec(problem_id: str) -> ProblemSpec:
    for spec in PROBLEM_REGISTRY:
        if spec.id == problem_id:
            return spec
    raise ValueError(f"No problem found for id: {problem_id}")


def spec_to_statement(spec: ProblemSpec) -> str:
    """
    Convert a problem spec to a statement.
    """
    hints_enabled = os.environ.get("HINTS", "none").lower() in ["all"]
    statement = spec.description
    
    if hints_enabled and len(spec.hints) > 0:
        hint_text = ""
        for hint_spec in spec.hints:
            hint_text += f"\n - {hint_spec.text}\n"
        statement += "\n\n" + f"<HINTS>{hint_text}</HINTS>"
    return template.replace("<STATEMENT>", statement)


# Implementation notes: setup_problem will only be called once per enviroment instance
@mcp.tool()
async def setup_problem(
    problem_id: str = Field(description="The id of the problem to solve"),
) -> str:
    """Starts the enviroment and returns the problem statement"""
    from .setup import git_setup

    spec = _get_spec(problem_id)

    logger.info(f"=== SETUP_PROBLEM DEBUG ===")
    logger.info(f"Problem ID: {problem_id}")
    logger.info(f"Spec: {spec}")

    logger.info(f"Setting up git repository at baseline commit: {spec.base}")
    git_setup(base_commit=spec.base, repo_path="/home/ubuntu/ClickHouse")
    logger.info("Git setup completed")

    if spec.setup:
        logger.info("Running custom setup function")
        config = spec.config or {}
        await spec.setup(config)
        logger.info("Custom setup completed")

    await start_dinit()
    # create the full statement
    return spec_to_statement(spec)


@click.command()
@click.argument("problem_id", envvar="PROBLEM_ID")
@click.option(
    "--workspace-dir",
    type=click.Path(),
    default=None,
    help="Optional path to reuse as the grading workspace. If omitted, a fresh temp dir is used.",
)
@click.option(
    "--reuse-workspace",
    is_flag=True,
    default=False,
    help="When --workspace-dir exists, reuse it (preserve caches) instead of recreating from scratch.",
)
@click.option(
    "--extra-logging",
    is_flag=True,
    default=False,
    help="Enable verbose, colorized logging for setup and subprocess commands.",
)
def setup_problem_script(
    problem_id: str,
    workspace_dir: str | None = None,
    reuse_workspace: bool = False,
    extra_logging: bool = False,
):
    """Set up a problem environment and return the problem statement."""
    global WORKSPACE_DIR, REUSE_WORKSPACE, EXTRA_LOGGING
    configure_logging(EXTRA_LOGGING)

    # Record workspace choices here too so a caller can prep once and reuse
    env_ws = os.environ.get("HUD_GRADE_WORKSPACE") or os.environ.get("HUD_GRADING_WORKSPACE")
    WORKSPACE_DIR = workspace_dir or env_ws
    REUSE_WORKSPACE = bool(
        reuse_workspace or (os.environ.get("HUD_REUSE_WORKSPACE", "").strip().lower() in {"1", "true", "yes", "on"})
    )
    EXTRA_LOGGING = bool(extra_logging or _truthy(os.environ.get("HUD_EXTRA_LOGGING")))
    if EXTRA_LOGGING:
        os.environ["HUD_EXTRA_LOGGING"] = "1"
    # Start dinit first
    asyncio.run(start_dinit())

    statement = asyncio.run(setup_problem(problem_id))
    print(statement)


# Implementation note: grade_problem will only be called once per enviroment instance
@mcp.tool()
async def grade_problem(
    problem_id: str,
    transcript: str | int = Field(description="The entire transcript produced by the model and its tool calls"),
) -> Grade:
    """Check your solution for grading. Returns a Grade object making sure to include all components that make up the score as subscores."""
    from .spec import Config

    spec = _get_spec(problem_id)

    # Create Config object with the required parameters
    config = Config(
        base=spec.base,
        test="",  # Not used for git tasks
        golden=spec.golden or [],
        problem_id=problem_id,
        test_files=spec.test_files,
    )

    # Invoke the solution function (e.g., git_squash_commits) to get a Grade
    logger.info(f"Calling solution function for problem {problem_id}")
    grade = spec.solution_fn(config)

    return grade


async def validate_problem(problem_id: str, per_test_files: bool = False) -> tuple[bool, str]:
    """
    Validate a problem by:
    1. Setup problem (reset to baseline)
    2. Grade problem (should get score 0.0)
    3. Run golden commands
    4. Grade problem again (should get score 1.0)

    Args:
        problem_id: The ID of the problem to validate
        per_test_files: Not used for git tasks (kept for compatibility)

    Returns:
        tuple[bool, str]: (success, result_message)
    """
    spec = _get_spec(problem_id)

    if not spec.golden:
        return False, f"Problem {problem_id} has no golden commands defined"

    logger.info(f"=== VALIDATING PROBLEM {problem_id} ===")

    # Step 1: Setup problem
    logger.info("Step 1: Setting up problem (reset to baseline)")
    await start_dinit()

    if spec.base and spec.base != "TODO":
        git_setup(base_commit=spec.base, repo_path="/home/ubuntu/ClickHouse")

    if spec.setup:
        config = spec.config or {}
        await spec.setup(config)

    # Step 2: Grade problem (should be 0.0)
    logger.info("Step 2: Grading problem before golden commands (expecting score 0.0)")
    from .spec import Config

    config_before = Config(
        base=spec.base,
        test="",
        golden=spec.golden or [],
        problem_id=problem_id,
        test_files=spec.test_files,
    )

    grade_before = spec.solution_fn(config_before)
    logger.info(f"Score before: {grade_before.score}")

    if grade_before.score != 0.0:
        return False, f"Expected score 0.0 before golden commands, got {grade_before.score}"

    # Step 3: Run golden commands
    logger.info("Step 3: Running golden commands")

    # Join all commands with && to run in a single shell session
    combined_command = " && ".join(spec.golden)
    for i, cmd in enumerate(spec.golden):
        logger.info(f"    {i+1}. {cmd}")

    result = subprocess.run(
        combined_command,
        shell=True,
        cwd="/home/ubuntu/ClickHouse",
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        error_msg = f"Golden commands failed\nStdout: {result.stdout}\nStderr: {result.stderr}"
        logger.error(error_msg)
        return False, error_msg

    if result.stdout:
        logger.debug(f"  Stdout: {result.stdout}")
    if result.stderr:
        logger.debug(f"  Stderr: {result.stderr}")

    # Step 4: Grade problem again (should be 1.0)
    logger.info("Step 4: Grading problem after golden commands (expecting score 1.0)")

    config_after = Config(
        base=spec.base,
        test="",
        golden=spec.golden or [],
        problem_id=problem_id,
        test_files=spec.test_files,
    )

    grade_after = spec.solution_fn(config_after)
    logger.info(f"Score after: {grade_after.score}")

    # Get actual tree hash for debugging
    try:
        tree_result = subprocess.run(
            "git rev-parse HEAD^{tree}",
            shell=True,
            cwd="/home/ubuntu/ClickHouse",
            capture_output=True,
            text=True,
        )
        actual_tree_hash = tree_result.stdout.strip() if tree_result.returncode == 0 else "unknown"
    except Exception:
        actual_tree_hash = "unknown"

    if grade_after.score != 1.0:
        result_msg = f"""Validation FAILED for {problem_id}
Score before: {grade_before.score} (expected 0.0) ✓
Score after: {grade_after.score} (expected 1.0) ✗

Actual tree hash after golden commands: {actual_tree_hash}

Grade details:
{grade_after}
"""
        return False, result_msg

    result_msg = f"""Validation PASSED for {problem_id}
Score before: {grade_before.score} (expected 0.0) ✓
Score after: {grade_after.score} (expected 1.0) ✓
"""
    return True, result_msg


@click.command()
@click.argument("problem_id", envvar="PROBLEM_ID")
@click.option("--output_path", type=click.Path(), default="/tmp/grade_result.json", help="Path to write the grade results to")
def grade_problem_script(
    problem_id: str,
    output_path: str,
):
    """Grade a problem solution and return the grade results."""

    configure_logging()
    transcript = "dummy transcript"
    grade = asyncio.run(grade_problem(problem_id, transcript))

    result = {
        "score": grade.score,
        "subscores": grade.subscores,
        "weights": grade.weights,
        "metadata": grade.metadata,
    }

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Score: {grade.score}")
    print(f"Subscores: {grade.subscores}")
    if grade.metadata:
        print(f"Metadata: {grade.metadata}")

@click.command()
@click.argument("problem_id", envvar="PROBLEM_ID")
@click.option(
    "--per-test-files",
    is_flag=True,
    default=False,
    help="Run full validation separately for each single test file of each test type",
)
def validate_problem_script(problem_id: str, per_test_files: bool):
    """Entry point for the validate_problem script."""
    configure_logging()
    # run the validate_problem function
    success, result = asyncio.run(validate_problem(problem_id, per_test_files=per_test_files))
    grade_str = str(result)
    if len(grade_str) > 2000:
        try:
            with open("/tmp/validate_problem.txt", "w") as f:
                f.write(grade_str)
        except Exception as e:
            logger.error(f"Failed to write full grade to /tmp/validate_problem.txt: {e}")
        print(grade_str[:2000])
    else:
        print(grade_str)
    sys.exit(0 if success else 1)


@click.command()
def main():
    configure_logging()
    # Initialize and run the server as root; you can use files and services that require root permissions
    # once init is done, the server will run as the model user to prevent it from accessing problem data
    mcp.run(transport="stdio")
