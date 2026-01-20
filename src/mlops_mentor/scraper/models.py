import base64
import os
from pathlib import Path
from subprocess import PIPE, Popen

import markdown2
import requests
from pydantic import BaseModel

from mlops_mentor.common import github_headers as headers


class RepoStats(BaseModel):
    """Model for repository statistics."""

    num_contributors: int | None
    num_prs: int | None
    num_commits_to_main: int | None
    average_commit_length_to_main: float | None
    latest_commit: str | None
    average_commit_length: float | None
    contributions_per_contributor: list[int] | None
    total_commits: int | None
    activity_matrix: list[list[int]] | None

    num_docker_files: int | None
    num_python_files: int | None
    num_workflow_files: int | None
    has_requirements_file: bool | None
    has_cloudbuild: bool | None
    using_dvc: bool | None
    repo_size: float | None
    readme_length: int | None
    actions_passing: bool | None

    num_warnings: int | None

    def __repr__(self):
        """Returns a string representation of the model."""
        return ",".join(f"0{d=}" for d in self.model_dump().items())


class Report(BaseModel):
    """Model for the report."""

    repo_api: str
    default_branch: str
    file_written: bool = False

    def download_checker(self) -> None:
        """Downloads the checker script from the repository."""
        if not Path("report.py").exists():
            url = "https://api.github.com/repos/SkafteNicki/dtu_mlops/contents/reports/report.py"
            response = requests.get(url, headers=headers, timeout=100)
            if response.status_code == 200:
                content_base64 = response.json()["content"]
                content_decoded = base64.b64decode(content_base64).decode("utf-8")
                with open("report.py", "w", encoding="utf-8") as file:
                    file.write(content_decoded)

    def download_report(self) -> None:
        """Downloads the report from the repository."""
        if self.file_written:
            return
        url = f"{self.repo_api}/contents/reports/README.md"
        response = requests.get(url, headers=headers, timeout=100).json()
        if response.get("message") != "Not Found" and response.get("status") != "404":
            content_base64 = response["content"]
            content_decoded = base64.b64decode(content_base64).decode("utf-8")

            out_path = Path("./output/README.md")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content_decoded, encoding="utf-8")
            self.file_written = True
        else:
            self.file_written = False

    @property
    def check_answers(self) -> int | None:
        """Returns the number of warnings in the report."""
        self.download_checker()
        self.download_report()
        if self.file_written:
            p = Popen(
                ["python", "report.py", "check"],
                cwd=".",
                stdout=PIPE,
                stderr=PIPE,
                stdin=PIPE,
            )
            if p.stderr is None:
                return None
            output = p.stderr.read()
            output = output.decode("utf-8").split("\n")
            lines = [line for line in output if "WARNING" in line]
            return len(lines)
        return None


class RepoContent(BaseModel):
    """Model for repository content."""

    repo_api: str
    default_branch: str

    @property
    def file_tree(self):
        """Returns the file tree of the repository."""
        if hasattr(self, "_file_tree"):
            return self._file_tree
        branch_url = f"{self.repo_api}/git/refs/heads/{self.default_branch}"
        branch_response = requests.get(branch_url, headers=headers, timeout=100).json()
        tree_sha = branch_response["object"]["sha"]
        tree_url = f"{self.repo_api}/git/trees/{tree_sha}?recursive=1"
        tree_response = requests.get(tree_url, headers=headers, timeout=100).json()
        self._file_tree = tree_response["tree"]
        return self._file_tree

    @property
    def num_docker_files(self) -> int:
        """Returns the number of Dockerfiles in the repository."""
        return len(
            [
                f
                for f in self.file_tree
                if "Dockerfile" in f["path"] or ".dockerfile" in f["path"]
            ]
        )

    @property
    def num_python_files(self) -> int:
        """Returns the number of Python files in the repository."""
        return len([f for f in self.file_tree if ".py" in f["path"]])

    @property
    def num_workflow_files(self) -> int:
        """Returns the number of workflow files in the repository."""
        return len(
            [
                f
                for f in self.file_tree
                if f["path"].startswith(".github/workflows/")
                and f["path"].endswith((".yml", ".yaml"))
            ]
        )

    @property
    def has_requirements_file(self) -> bool:
        """Returns True if the repository has a requirements.txt or uv.lock file"""
        has_uv = any("uv.lock" in f["path"] for f in self.file_tree)
        has_req = any("requirements.txt" in f["path"] for f in self.file_tree)
        return any(has_uv, has_req)

    @property
    def has_cloudbuild(self) -> bool:
        """Returns True if the repository uses Google Cloud Build."""
        return any(
            os.path.basename(f["path"]) == "cloudbuild.yaml" for f in self.file_tree
        )

    @property
    def using_dvc(self) -> bool:
        """Returns True if the repository uses DVC."""
        return any(".dvc" in f["path"] for f in self.file_tree)

    @property
    def repo_size(self) -> float:
        """Returns the size of the repository in MB."""
        total_size_bytes = sum([f["size"] for f in self.file_tree if "size" in f])
        return total_size_bytes / (1024**2)

    @property
    def readme_length(self) -> int:
        """Returns the number of words in the README file."""
        readme_url = f"{self.repo_api}/readme"
        readme_response = requests.get(readme_url, headers=headers, timeout=100).json()
        if "content" in readme_response:
            content_base64 = readme_response["content"]
            content_decoded = base64.b64decode(content_base64).decode("utf-8")
            plain_text = markdown2.markdown(content_decoded, extras=["strip"])
            return len(plain_text.split())
        return 0

    @property
    def actions_passing(self) -> bool:
        """Returns True if the GitHub Actions are passing."""
        commit_url = f"{self.repo_api}/commits/{self.default_branch}"
        commit_response = requests.get(commit_url, headers=headers, timeout=100).json()
        latest_commit = commit_response["sha"]

        workflow_url = (
            f"{self.repo_api}/actions/runs?branch={self.default_branch}&event=push"
        )
        workflow_response = requests.get(
            workflow_url, headers=headers, timeout=100
        ).json()
        workflow_runs = workflow_response["workflow_runs"]

        all_passing = True
        for w_run in workflow_runs:
            if w_run["head_sha"] == latest_commit and (
                w_run["status"] != "completed" or w_run["conclusion"] != "success"
            ):
                all_passing = False
                break
        return all_passing
