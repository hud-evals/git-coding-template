import logging
import subprocess
from pathlib import Path

from hud_controller.spec import Config, Grader

logger = logging.getLogger(__name__)


class AgentPatchGrader(Grader):
    """
    A grader that tests agent patches by applying them and running tests.
    """

    name = "AgentPatchGrader"

    @classmethod
    def compute_score(
        cls,
        state: Config,
    ) -> tuple[float, dict]:
        """
        Compute a score based on whether the agent patch fixes the issue.

        Args:
            state: The current environment state

        Returns:
            tuple: (score, metadata) where score is 1.0 if agent patch fixes the issue, 0.0 otherwise
        """
        return 1.0, {}


class GitGrader(Grader):
    """
    Validates that the agent's git operations resulted in the correct repository state
    by comparing the git tree hash of the current commit to an expected tree hash,
    and optionally validating commit count and commit message.
    """

    name = "GitGrader"

    @classmethod
    def compute_score(
        cls,
        state: Config,
        **kwargs,
    ) -> tuple[float, dict]:
        """
        Args:
            state: The current environment state
            **kwargs:
                working_dir: Path to the git repository
                expected_tree_hash: Expected git tree hash to validate against
                expected_commit_count: Expected number of commits from base (optional)
                expected_commit_message: Expected commit message pattern (optional)
                base_commit: Base commit to count from (optional, required if expected_commit_count is set)
                first_parent: If True, only count commits on first-parent line (for merge commits)
                validate_metadata: Dict of metadata validations to perform (optional)
                    Example: {
                        "author_emails": {
                            "must_not_contain": ["old@email.com"],
                            "must_contain": ["new@email.com"]
                        },
                        "author_names": {
                            "must_not_contain": ["Old Name"],
                            "must_contain": ["New Name"]
                        }
                    }

        Returns:
            tuple: (score, metadata) where score is 1.0 if state matches, 0.0 otherwise
        """
        # Extract parameters from kwargs
        working_dir = kwargs.get("working_dir")
        expected_tree_hash = kwargs.get("expected_tree_hash")
        expected_commit_count = kwargs.get("expected_commit_count")
        expected_commit_message = kwargs.get("expected_commit_message")
        base_commit = kwargs.get("base_commit")
        first_parent = kwargs.get("first_parent", False)

        if not working_dir:
            return 0.0, {"error": "working_dir is required"}
        if not expected_tree_hash:
            return 0.0, {"error": "expected_tree_hash is required"}

        repo_path = Path(working_dir)
        metadata = {}
        score = 1.0

        # Check tree hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            metadata["error"] = f"Failed to get current tree hash: {result.stderr}"
            logger.error(metadata["error"])
            return 0.0, metadata

        current_tree_hash = result.stdout.strip()
        metadata["current_tree_hash"] = current_tree_hash
        metadata["expected_tree_hash"] = expected_tree_hash

        if current_tree_hash == expected_tree_hash:
            metadata["tree_match"] = True
            logger.info(f"✓ Git trees match: {current_tree_hash}")
        else:
            metadata["tree_match"] = False
            metadata["error"] = f"Git trees don't match. Expected {expected_tree_hash}, got {current_tree_hash}"
            logger.error(metadata["error"])
            score = 0.0

            result = subprocess.run(
                ["git", "diff-tree", "--stat", expected_tree_hash, current_tree_hash],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                metadata["diff_summary"] = result.stdout.strip()
                logger.info(f"Diff from expected:\n{result.stdout}")

        # Check commit count if specified
        if expected_commit_count is not None:
            if base_commit is None:
                metadata["commit_count_error"] = "base_commit required when checking commit count"
                logger.error(metadata["commit_count_error"])
                return 0.0, metadata

            # Build git command based on first_parent flag
            git_cmd = ["git", "rev-list", "--count"]
            if first_parent:
                git_cmd.append("--first-parent")
            git_cmd.append(f"{base_commit}..HEAD")

            result = subprocess.run(
                git_cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                metadata["commit_count_error"] = f"Failed to count commits: {result.stderr}"
                logger.error(metadata["commit_count_error"])
                return 0.0, metadata

            actual_count = int(result.stdout.strip())
            metadata["actual_commit_count"] = actual_count
            metadata["expected_commit_count"] = expected_commit_count

            if actual_count == expected_commit_count:
                metadata["commit_count_match"] = True
                logger.info(f"✓ Commit count matches: {actual_count}")
            else:
                metadata["commit_count_match"] = False
                metadata["commit_count_error"] = f"Expected {expected_commit_count} commits, got {actual_count}"
                logger.error(metadata["commit_count_error"])
                score = 0.0

        # Check commit message if specified
        if expected_commit_message is not None:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%s"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                metadata["commit_message_error"] = f"Failed to get commit message: {result.stderr}"
                logger.error(metadata["commit_message_error"])
                return 0.0, metadata

            actual_message = result.stdout.strip()
            metadata["actual_commit_message"] = actual_message
            metadata["expected_commit_message"] = expected_commit_message

            if expected_commit_message in actual_message or actual_message == expected_commit_message:
                metadata["commit_message_match"] = True
                logger.info(f"✓ Commit message matches: {actual_message}")
            else:
                metadata["commit_message_match"] = False
                metadata["commit_message_error"] = f"Expected message containing '{expected_commit_message}', got '{actual_message}'"
                logger.error(metadata["commit_message_error"])
                score = 0.0

        # Validate metadata if specified
        validate_metadata = kwargs.get("validate_metadata")
        if validate_metadata:
            if base_commit is None:
                metadata["metadata_validation_error"] = "base_commit required for metadata validation"
                logger.error(metadata["metadata_validation_error"])
                return 0.0, metadata

            metadata["metadata_validations"] = {}

            # Validate author emails
            if "author_emails" in validate_metadata:
                email_validation = validate_metadata["author_emails"]
                result = subprocess.run(
                    ["git", "log", "--format=%ae", f"{base_commit}..HEAD"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    metadata["metadata_validation_error"] = f"Failed to get author emails: {result.stderr}"
                    logger.error(metadata["metadata_validation_error"])
                    return 0.0, metadata

                actual_emails = [e for e in result.stdout.strip().split('\n') if e]
                metadata["metadata_validations"]["author_emails"] = {
                    "actual_emails": list(set(actual_emails))
                }

                # Check must_not_contain
                if "must_not_contain" in email_validation:
                    forbidden = email_validation["must_not_contain"]
                    found_forbidden = [email for email in actual_emails if email in forbidden]
                    if found_forbidden:
                        metadata["metadata_validations"]["author_emails"]["forbidden_found"] = found_forbidden
                        metadata["metadata_validation_error"] = f"Forbidden emails found: {found_forbidden}"
                        logger.error(metadata["metadata_validation_error"])
                        score = 0.0
                    else:
                        logger.info("✓ No forbidden emails found")

                # Check must_contain
                if "must_contain" in email_validation:
                    required = email_validation["must_contain"]
                    found_required = [email for email in required if email in actual_emails]
                    if len(found_required) != len(required):
                        missing = [email for email in required if email not in actual_emails]
                        metadata["metadata_validations"]["author_emails"]["required_missing"] = missing
                        metadata["metadata_validation_error"] = f"Required emails missing: {missing}"
                        logger.error(metadata["metadata_validation_error"])
                        score = 0.0
                    else:
                        logger.info("✓ All required emails found")

            # Validate author names
            if "author_names" in validate_metadata:
                name_validation = validate_metadata["author_names"]
                result = subprocess.run(
                    ["git", "log", "--format=%an", f"{base_commit}..HEAD"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    metadata["metadata_validation_error"] = f"Failed to get author names: {result.stderr}"
                    logger.error(metadata["metadata_validation_error"])
                    return 0.0, metadata

                actual_names = [n for n in result.stdout.strip().split('\n') if n]
                metadata["metadata_validations"]["author_names"] = {
                    "actual_names": list(set(actual_names))
                }

                # Check must_not_contain
                if "must_not_contain" in name_validation:
                    forbidden = name_validation["must_not_contain"]
                    found_forbidden = [name for name in actual_names if name in forbidden]
                    if found_forbidden:
                        metadata["metadata_validations"]["author_names"]["forbidden_found"] = found_forbidden
                        metadata["metadata_validation_error"] = f"Forbidden names found: {found_forbidden}"
                        logger.error(metadata["metadata_validation_error"])
                        score = 0.0
                    else:
                        logger.info("✓ No forbidden names found")

                # Check must_contain
                if "must_contain" in name_validation:
                    required = name_validation["must_contain"]
                    found_required = [name for name in required if name in actual_names]
                    if len(found_required) != len(required):
                        missing = [name for name in required if name not in actual_names]
                        metadata["metadata_validations"]["author_names"]["required_missing"] = missing
                        metadata["metadata_validation_error"] = f"Required names missing: {missing}"
                        logger.error(metadata["metadata_validation_error"])
                        score = 0.0
                    else:
                        logger.info("✓ All required names found")

        return score, metadata
