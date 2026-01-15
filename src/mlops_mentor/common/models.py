import requests
from loguru import logger
from pydantic import BaseModel

from mlops_mentor.common import github_headers as headers


class Contributor(BaseModel):
    """Model for contributors."""

    login: str
    contributions: int
    commits_pr: int

    @property
    def total_commits(self) -> int:
        """Returns the total number of commits by the contributor."""
        return self.contributions + self.commits_pr


class RepoInfo(BaseModel):
    """Model for group information."""

    repo_url: str

    @property
    def is_accessible(self) -> bool:
        """Returns True if the repository is accessible."""
        if hasattr(self, "_repo_accessible") and self._repo_accessible is not None:
            return self._repo_accessible

        try:
            response = requests.head(
                self.repo_url, headers=headers, timeout=100, allow_redirects=False
            )

            if 300 <= response.status_code < 400:  # Check if redirection occurred
                redirect_url = response.headers.get("Location")
                if redirect_url:
                    self.repo_url = (
                        redirect_url  # Update the repository URL to the redirected one
                    )

            self._repo_accessible = (
                requests.head(self.repo_url, headers=headers, timeout=100).status_code
                == 200
            )
        except requests.RequestException as e:
            logger.error(f"An error occurred: {e}")
            self._repo_accessible = False

        return self._repo_accessible

    @property
    def repo_api(self) -> str:
        """Returns the API URL of the repository."""
        split = self.repo_url.split("/")
        return f"https://api.github.com/repos/{split[-2]}/{split[-1]}"

    @property
    def default_branch(self) -> str:
        """Returns the default branch of the repository."""
        if hasattr(self, "_default_branch"):
            return self._default_branch
        self._default_branch = requests.get(
            self.repo_api, headers=headers, timeout=100
        ).json()["default_branch"]
        return self._default_branch

    @property
    def contributors(self) -> list[Contributor]:
        """Returns all contributors to the repository."""
        request = requests.get(
            f"{self.repo_api}/contributors", headers=headers, timeout=100
        ).json()
        return [
            Contributor(
                login=c["login"], contributions=c["contributions"], commits_pr=0
            )
            for c in request
        ]

    @property
    def prs(self) -> list:
        """Returns all pull requests to the repository."""
        prs = []
        page_counter = 1
        while True:
            request = requests.get(
                f"{self.repo_api}/pulls",
                headers=headers,
                timeout=100,
                params={"state": "all", "page": page_counter, "per_page": 100},
            ).json()
            if len(request) == 0:
                break
            page_counter += 1
            prs.extend(request)
        return prs

    @property
    def commits(self) -> list:
        """Returns all commits to the default branch."""
        commits = []
        page_counter = 1
        while True:
            request = requests.get(
                f"{self.repo_api}/commits",
                headers=headers,
                timeout=100,
                params={"page": page_counter, "per_page": 100},
            ).json()
            if len(request) == 0:
                break
            page_counter += 1
            commits.extend(request)
        return commits

    @property
    def latest_commit_sha(self) -> str:
        """Returns the SHA of the latest commit on the default branch."""
        if hasattr(self, "_latest_commit_sha"):
            return self._latest_commit_sha
        response = requests.get(
            f"{self.repo_api}/commits/{self.default_branch}",
            headers=headers,
            timeout=100,
        ).json()
        self._latest_commit_sha = response["sha"]
        return self._latest_commit_sha


class GroupInfo(BaseModel):
    """Model for group information."""

    group_number: int
    student_1: str | None
    student_2: str | None
    student_3: str | None
    student_4: str | None
    student_5: str | None
    repo_info: RepoInfo
