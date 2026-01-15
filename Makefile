run:
	uv run --env-file .env src/mlops_mentor/run.py
scrape:
	uv run --env-file .env src/mlops_mentor/scraper/main.py scrape

formatting:
	uvx ruff check src/

leaderboard:
	uv run src/mlops_mentor/leaderboard/app.py