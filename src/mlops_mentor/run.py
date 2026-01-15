import time

from datasets import Dataset, load_dataset
from loguru import logger

from mlops_mentor.common.data import load_groups
from mlops_mentor.llm_judge import codebase
from mlops_mentor.scraper import scrape

if __name__ == "__main__":
    groups = load_groups("group_info.csv")

    # Try to load existing dataset
    try:
        logger.info("Loading existing dataset from hub...")
        existing_dataset = load_dataset("rasgaard/mlops-repo-evaluations", private=True)
        results = list(existing_dataset["train"])
        logger.info(f"Loaded {len(results)} existing entries")

        # Get set of already processed repo+commit combinations to avoid duplicates
        processed_entries = {
            (entry["repo_url"], entry.get("commit_sha"))
            for entry in results
            if entry.get("commit_sha")  # Only track entries with commit SHA
        }
    except Exception as e:
        logger.warning(f"Could not load existing dataset: {e}")
        logger.info("Starting with empty dataset")
        results = []
        processed_entries = set()
    for group in groups:
        if not group.repo_info.is_accessible:
            logger.warning(
                f"Skipping inaccessible repository: {group.repo_info.repo_url}"
            )
            continue

        repo_url = group.repo_info.repo_url

        # Get the latest commit SHA
        try:
            commit_sha = group.repo_info.latest_commit_sha
            logger.info(f"Latest commit SHA for {repo_url}: {commit_sha}")
        except Exception as e:
            logger.error(f"Failed to get commit SHA for {repo_url}: {e}")
            continue

        # Skip if this repo+commit combination has already been processed
        if (repo_url, commit_sha) in processed_entries:
            logger.info(
                f"Skipping already processed repository at commit: {repo_url} ({commit_sha[:7]})"
            )
            continue

        group_results = {
            "timestamp": time.time(),
            "group_number": group.group_number,
            "repo_url": repo_url,
            "commit_sha": commit_sha,
        }
        print(f"Scraping repository: {repo_url}")
        stats = scrape(repo_url)
        print(f"Repository stats: {stats}")
        group_results["stats"] = stats.model_dump_json()

        print(f"Evaluating codebase for repository: {repo_url}")
        evaluation = codebase(repo_url)
        print(f"Codebase evaluation: {evaluation}")
        group_results["evaluation"] = evaluation.model_dump_json()

        results.append(group_results)

    dataset = Dataset.from_list(results)
    dataset.push_to_hub("rasgaard/mlops-repo-evaluations", private=True)
