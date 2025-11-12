# Agent Evaluation Framework Template

## Overview

This is a template framework for creating and evaluating AI agent tasks. It provides a structured approach to:
- Define coding tasks with clear specifications
- Grade agent solutions automatically using test-based validation
- Manage multiple task difficulties (easy, medium, hard)
- Run tasks in isolated environments with proper grading

## Project Structure

```
.
├── src/hud_controller/          # Main framework code
│   ├── app.py                   # Main MCP server and entry points
│   ├── spec.py                  # Core specifications (Problem, Grade, Grader)
│   ├── graders.py               # Grading logic
│   ├── utils.py                 # Utility functions
│   ├── setup.py                 # Environment setup
│   ├── problems/                # Task definitions by difficulty
│   │   ├── tasks.py             # Easy difficulty tasks
│   └── tools/                   # MCP tools for testing
│       ├── base.py              # Base tool definitions
│       ├── bash.py              # Bash execution
│       ├── edit.py              # File editing
│       └── run.py               # Command running
├── pyproject.toml               # Python package configuration
├── Dockerfile                   # Container setup
└── README.md                    # This file
```

## Core Concepts

### 1. Problem Definition

Problems are defined using the `@problem` annotation with these key fields:

```python
@problem(
    id="squash-commits-first-parent", # the problem id (required)
    description="Squash all commits in `master` after `2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16` (following first-parent history) into a single commit.", # the prompt for the agent
    hints=[], # any hints you want to give
    difficulty="easy",
    task_type="git",
    review_level="no-review",
    base="cafc904fc34cc78e51c459ea86dd981486ae0589", # how to initialize the agent
    test_files=None,
    golden=[ # the golden sequence of commands to get to the desired end state. Needed for validation
        "cd /home/ubuntu/ClickHouse",
        "GIT_SEQUENCE_EDITOR='sed -i \"2,\\$s/^pick/squash/\"' GIT_EDITOR='sed -i \"1s/.*/Squashed commits/; 2,\\$d\"' git rebase -i 2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16",
    ],
)
def git_squash_commits_first_parent(state: Config) -> Grade:
    """
    Grade the git squash commits task using first-parent counting.

    Validates that the agent properly squashed 5 commits into 1 using interactive rebase.
    Uses --first-parent to count commits (matching git rebase -i HEAD~5 behavior).

    Checks:
    - Tree hash matches (files are correct after squash)
    - Only 1 commit exists since HEAD~5 on first-parent line
    """
    return Grade.from_subscores([
        GitGrader.grade(
            state=state,
            working_dir="/home/ubuntu/ClickHouse",
            expected_tree_hash="97f674f0359a4dfb3fb815bda90b105ca3b12413",
            expected_commit_count=1,
            base_commit="2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16",
            first_parent=True,
            weight=1.0,
        ),
    ])
```

## Creating New Tasks

### Step 1: Prepare Git Repository

You'll need to prepare a git repository with a desired starting state and ideally a desired end state. 
The start state is represented by the `base` field in the @problem. The end state is represented by the tree hash at the end.

### Step 2: Define the Task

We currently only have src/hud_controller/problems/tasks.py, but feel free to make more files in the subdirectory.
Once you do that, you can add a problem to the registry as follows:

```python
@problem(
    id="squash-commits-first-parent", # the problem id (required)
    description="Squash all commits in `master` after `2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16` (following first-parent history) into a single commit.", # the prompt for the agent
    hints=[], # any hints you want to give
    difficulty="easy",
    task_type="git",
    review_level="no-review",
    base="cafc904fc34cc78e51c459ea86dd981486ae0589", # how to initialize the agent
    test_files=None,
    golden=[ # the golden sequence of commands to get to the desired end state. Needed for validation
        "cd /home/ubuntu/ClickHouse",
        "GIT_SEQUENCE_EDITOR='sed -i \"2,\\$s/^pick/squash/\"' GIT_EDITOR='sed -i \"1s/.*/Squashed commits/; 2,\\$d\"' git rebase -i 2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16",
    ],
)
def git_squash_commits_first_parent(state: Config) -> Grade:
    """
    Grade the git squash commits task using first-parent counting.

    Validates that the agent properly squashed 5 commits into 1 using interactive rebase.
    Uses --first-parent to count commits (matching git rebase -i HEAD~5 behavior).

    Checks:
    - Tree hash matches (files are correct after squash)
    - Only 1 commit exists since HEAD~5 on first-parent line
    """

    # you can theoretically use multiple subgraders, but we reccomend only using gitgrader
    return Grade.from_subscores([
        GitGrader.grade(
            state=state,
            working_dir="/home/ubuntu/ClickHouse",
            expected_tree_hash="97f674f0359a4dfb3fb815bda90b105ca3b12413",
            expected_commit_count=1,
            base_commit="2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16",
            first_parent=True,
            weight=1.0,
        ),
    ])
```
### Step 3: Validate your problem

It's important to ensure that your problems pass a basic sanity check:
* Before the golden commands are appleid, the grader should fail.
* After the commands are applied, the grader should pass

To help you with this, we have a script called `utils/imagectl3.py`.

To run and build the images you can do:
```bash
uv run utils/imagectl3.py git_ --build --validate
```
You can specify the exact image you want to test with the `--ids` flag. 
You can also make this easier to type by using the shorform `-b` flag for `--build` and the shortform `-v` flag for `--validate`.
```bash
uv run utils/imagectl3.py git_ -bv --ids squash-commits-first-parent
```
Note: ensure your image is built before you try to validate it.

## Running Tasks

### Setup Environment

```bash
uv sync
```
### Build, Validate all problems and generate Json

```bash
uv run utils/imagectl3.py git_ -bvj
```
This will build all the docker images, with the prefix `git_` and then run the validation workflow. 
Once you get a lot of problems, you'll find it helpful to do building and validation in parallel with `--jobs`:
```bash
uv run utils/imagectl3.py git_ -bvj --jobs 4
```

### Run hud eval locally
You can run the images locally with:
```
uv run hud eval local-hud.json claude --max-steps 50
```

### Run hud eval remotely
You can run them remotely too! However, you'll need to push the images. T
To make this easier, we have the `--push` or `-p` flag in imagectl3. 
Note that we also change the image prefix to make it pushable to docker hub.
```bash
uv run utils/imagectl3.py govindhud/git_ -bvjp --jobs 4
```
Once all images are pushed, we can:
```
uv run hud eval remote-hud.json claude --max-steps 50
```


## Configuration

### Environment Variables

Key environment variables used by the grading system:

- `MCP_TESTING_MODE` - Enable testing tools (default: "1")

### Docker Configuration

The included `Dockerfile` sets up the complete environment:
- Base system with required tools
- VNC for GUI testing (if needed)

