import logging
import subprocess
from typing import Any

from hud_controller.graders import GitGrader
from hud_controller.spec import Config, Grade, problem

logger = logging.getLogger(__name__)


@problem(
    id="squash-commits-first-parent",
    description="Squash all commits in `master` after `2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16` (following first-parent history) into a single commit.",
    pr_number=None,
    hints=[],
    difficulty="easy",
    task_type="git",
    review_level="no-review",
    base="cafc904fc34cc78e51c459ea86dd981486ae0589",
    test_files=None,
    golden=[
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


@problem(
    id="squash-commits-all-history",
    description="Squash all commits since `2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16` into a single commit. Count commits including merged branches (not just first-parent).",
    pr_number=None,
    hints=[],
    difficulty="easy",
    task_type="git",
    review_level="no-review",
    base="cafc904fc34cc78e51c459ea86dd981486ae0589",
    test_files=None,
    golden=[
        "cd /home/ubuntu/ClickHouse",
        "git reset --soft 2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16",
        "git commit -m 'Squashed commits'",
    ],
)
def git_squash_commits_all_history(state: Config) -> Grade:
    """
    Grade the git squash commits task using full history counting.

    Validates that the agent properly squashed 14 commits into 1.
    Counts ALL commits (not just first-parent), including merged feature branches.

    Checks:
    - Tree hash matches (files are correct after squash)
    - Only 1 commit exists since the base (all 14 commits were squashed to 1)
    """
    return Grade.from_subscores([
        GitGrader.grade(
            state=state,
            working_dir="/home/ubuntu/ClickHouse",
            expected_tree_hash="97f674f0359a4dfb3fb815bda90b105ca3b12413",
            expected_commit_count=1,
            base_commit="2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16",
            first_parent=False,
            weight=1.0,
        ),
    ])


@problem(
    id="amend-old-commit",
    description="Add the exact line `# TODO: Change this email` to the end of the README.md file in commit `4e2e5799753` (fix logical error when low cardinality use statistics). The subsequent commits should remain unchanged.",
    pr_number=None,
    hints=[],
    difficulty="medium",
    task_type="git",
    review_level="no-review",
    base="cafc904fc34cc78e51c459ea86dd981486ae0589",
    test_files=None,
    golden=[
        "cd /home/ubuntu/ClickHouse",
        "GIT_SEQUENCE_EDITOR='sed -i \"/4e2e5799753/s/^pick/edit/\"' git rebase -i 2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16",
        "echo '# TODO: Change this email' >> README.md",
        "git add README.md",
        "GIT_EDITOR=true git commit --amend --no-edit",
        "GIT_EDITOR=true git rebase --continue",
    ],
)
def git_amend_old_commit(state: Config) -> Grade:
    """
    Validates that the agent properly amended an old commit using interactive rebase.
    Checks that the README.md change is present in the correct commit and all commits are preserved.

    Checks:
    - Tree hash matches (README.md has the new line and all other files are correct)
    - Commit count remains the same (no commits lost during rebase)
    """
    return Grade.from_subscores([
        GitGrader.grade(
            state=state,
            working_dir="/home/ubuntu/ClickHouse",
            expected_tree_hash="f77f602f849981b664d92004fe8534182005e3c9",
            expected_commit_count=8,
            base_commit="2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16",
            first_parent=True,
            weight=1.0,
        ),
    ])


@problem(
    id="cherry-pick-merge-commits",
    description="Create a new branch called `release-branch` from commit `2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16`, then cherry-pick this merge commit from master: 634b7ba69fc492f0894559bac901d9ee1b2a20ce",
    pr_number=None,
    hints=[],
    difficulty="medium",
    task_type="git",
    review_level="no-review",
    base="cafc904fc34cc78e51c459ea86dd981486ae0589",
    test_files=None,
    golden=[
        "cd /home/ubuntu/ClickHouse",
        "git checkout -b release-branch 2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16",
        "git cherry-pick -m 1 634b7ba69fc492f0894559bac901d9ee1b2a20ce",
    ],
)
def git_cherry_pick_merge_commits(state: Config) -> Grade:
    """
    Grade the cherry-pick merge commits task.

    Validates that the agent properly cherry-picked a merge commit using -m flag onto a new branch.
    This is a realistic backporting scenario where you create a release branch and cherry-pick fixes.

    Checks:
    - Tree hash matches (changes from the merge are present)
    - Exactly 1 commit added on the release branch
    """
    return Grade.from_subscores([
        GitGrader.grade(
            state=state,
            working_dir="/home/ubuntu/ClickHouse",
            expected_tree_hash="b329cdbab4993963108151f56c1189077cf28443",
            expected_commit_count=1,
            base_commit="2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16",
            first_parent=True,
            weight=1.0,
        ),
    ])


@problem(
    id="rewrite-author-emails",
    description="""The repository has commits from contributors using personal emails. Rewrite the git history
to change the following emails (both author and committer emails) to company emails for all commits after `2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16`:

- Change `a3at.mail@gmail.com` to `a.khuzhin@clickhouse.com`
- Change `hanfei19910905@gmail.com` to `han.fei@clickhouse.com`""",
    pr_number=None,
    hints=[],
    difficulty="medium",
    task_type="git",
    review_level="no-review",
    base="cafc904fc34cc78e51c459ea86dd981486ae0589",
    test_files=None,
    golden=[
        "cd /home/ubuntu/ClickHouse",
        """git filter-branch --force --env-filter '
if [ "$GIT_AUTHOR_EMAIL" = "a3at.mail@gmail.com" ]; then
    export GIT_AUTHOR_EMAIL="a.khuzhin@clickhouse.com"
fi
if [ "$GIT_AUTHOR_EMAIL" = "hanfei19910905@gmail.com" ]; then
    export GIT_AUTHOR_EMAIL="han.fei@clickhouse.com"
fi
if [ "$GIT_COMMITTER_EMAIL" = "a3at.mail@gmail.com" ]; then
    export GIT_COMMITTER_EMAIL="a.khuzhin@clickhouse.com"
fi
if [ "$GIT_COMMITTER_EMAIL" = "hanfei19910905@gmail.com" ]; then
    export GIT_COMMITTER_EMAIL="han.fei@clickhouse.com"
fi
' --tag-name-filter cat -- 2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16..HEAD""",
        "rm -rf .git/refs/original/",
        "git reflog expire --expire=now --all",
        "git gc --prune=now",
    ],
)
def git_rewrite_author_emails(state: Config) -> Grade:
    """
    Grade the rewrite author emails task.

    Validates that the agent properly used git filter-branch to rewrite author information.

    Checks:
    - Tree hash matches (content unchanged, only metadata rewritten)
    - Commit count matches (5 commits in first-parent history)
    """
    return Grade.from_subscores([
        GitGrader.grade(
            state=state,
            working_dir="/home/ubuntu/ClickHouse",
            expected_tree_hash="97f674f0359a4dfb3fb815bda90b105ca3b12413",
            expected_commit_count=5,
            base_commit="2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16",
            first_parent=True,
            validate_metadata={
                "author_emails": {
                    "must_not_contain": ["a3at.mail@gmail.com", "hanfei19910905@gmail.com"],
                    "must_contain": ["a.khuzhin@clickhouse.com", "han.fei@clickhouse.com"],
                }
            },
            weight=1.0,
        ),
    ])


@problem(
    id="update-submodule-commit",
    description="There's a bug in the `contrib/zstd` submodule, roll it back to its parent commit.",
    pr_number=None,
    hints=[],
    difficulty="medium",
    task_type="git",
    review_level="no-review",
    base="cafc904fc34cc78e51c459ea86dd981486ae0589",
    test_files=None,
    golden=[
        "cd /home/ubuntu/ClickHouse",
        "git submodule update --init contrib/zstd",
        "git config --global --add safe.directory /home/ubuntu/ClickHouse/contrib/zstd",
        "cd contrib/zstd",
        "git checkout HEAD~1",
        "cd /home/ubuntu/ClickHouse",
        "git add contrib/zstd",
        "git commit -m 'Rollback zstd submodule to previous commit'",
    ],
)
def git_update_submodule_commit(state: Config) -> Grade:
    """
    Grade the submodule update task.

    Validates that the agent properly updated a git submodule to a specific commit.
    This tests understanding of submodule mechanics, which many developers struggle with.

    Checks:
    - Tree hash matches (submodule pointer updated correctly)
    - Exactly 1 commit added (the submodule update commit)
    """
    return Grade.from_subscores([
        GitGrader.grade(
            state=state,
            working_dir="/home/ubuntu/ClickHouse",
            expected_tree_hash="fe6e961c8e2bac7ca5bad137f4e3e18eed9dc995",
            expected_commit_count=1,
            base_commit="cafc904fc34cc78e51c459ea86dd981486ae0589",
            first_parent=True,
            weight=1.0,
        ),
    ])


async def setup_broken_merge_state(config: dict[str, Any]) -> None:  # noqa: ARG001
    """Create a broken state from a bad merge that needs to be undone using reflog."""
    repo_path = "/home/ubuntu/ClickHouse"

    commands = [
        "git checkout -b refactor-rng",
        # Attempt to add lazy initialization but incomplete
        """cat > src/Common/thread_local_rng.cpp << 'EOF'
#include <Common/thread_local_rng.h>
#include <Common/randomSeed.h>
#include <memory>

// Refactor: Lazy initialization to improve thread creation performance
namespace
{
    struct RNGInitializer
    {
        pcg64* rng;

        RNGInitializer()
        {
            rng = new pcg64(randomSeed());
        }

        pcg64& get()
        {
            return *rng;
        }
    };
}

thread_local RNGInitializer thread_local_rng_impl;

pcg64 thread_local_rng = thread_local_rng_impl.get();
EOF""",
        "git add src/Common/thread_local_rng.cpp",
        "git commit -m 'Refactor: Add lazy initialization for thread local RNG (WIP)'",
        # Go back to main and merge it by mistake
        "git checkout -",
        "git merge --no-ff refactor-rng -m 'Merge refactor-rng'",
        # Delete the feature branch
        "git branch -D refactor-rng",
    ]

    for cmd in commands:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error(f"Setup command failed: {cmd}")
            logger.error(f"Error: {result.stderr}")


@problem(
    id="recover-from-bad-merge",
    description="A colleague attempted to refactor `src/Common/thread_local_rng.cpp` to use lazy initialization but the refactor was incomplete and has compilation errors. The refactor branch was accidentally merged and then deleted. Please restore the branch to the state before the merge.",
    pr_number=None,
    hints=[],
    difficulty="hard",
    task_type="git",
    review_level="no-review",
    base="cafc904fc34cc78e51c459ea86dd981486ae0589",
    test_files=None,
    setup=setup_broken_merge_state,
    golden=[
        "cd /home/ubuntu/ClickHouse",
        "git reflog",
        # Need to go back before the merge
        # HEAD@{0} = current (after merge)
        # HEAD@{1} = merge
        # HEAD@{2} = checkout back to original branch
        # HEAD@{3} = before any of this happened (the good state)
        "git reset --hard HEAD@{3}",
    ],
)
def git_recover_from_bad_merge(state: Config) -> Grade:
    """
    Grade the recovery from bad merge task.

    This tests whether the agent can:
    1. Understand and navigate git reflog
    2. Identify the commit state before the bad merge
    3. Use git reset --hard with reflog references to restore state
    4. Verify the branch is in the correct state

    Checks:
    - Tree hash matches the original state (before merge)
    - Exactly 5 commits exist after base
    """
    return Grade.from_subscores([
        GitGrader.grade(
            state=state,
            working_dir="/home/ubuntu/ClickHouse",
            expected_tree_hash="97f674f0359a4dfb3fb815bda90b105ca3b12413",
            expected_commit_count=5,
            base_commit="2d0bfff1ffba4a6ac8ee3fbcff7f7624cf2f0f16",
            first_parent=True,
            weight=1.0,
        ),
    ])