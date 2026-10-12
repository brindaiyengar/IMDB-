"""Publish the dashboard to Hugging Face.

  python deploy/deploy_hf.py <hf-username>

1. Uploads .imdb_cache/*.parquet + meta.json to a PRIVATE dataset repo.
2. Uploads the app code to a Docker Space and sets the variables it needs.
Requires `hf auth login` with a write token.
"""
import sys
from pathlib import Path

from huggingface_hub import HfApi, get_token

ROOT = Path(__file__).resolve().parent.parent
user = sys.argv[1]
data_repo = f"{user}/imdb-movie-analytics-data"
space_repo = f"{user}/imdb-movie-analytics"
api = HfApi()

api.create_repo(data_repo, repo_type="dataset", private=True, exist_ok=True)
api.upload_folder(repo_id=data_repo, repo_type="dataset", folder_path=ROOT / ".imdb_cache",
                  allow_patterns=["*.parquet", "meta.json"],
                  commit_message="Prepared IMDb data")
print("data:", f"https://huggingface.co/datasets/{data_repo}")

api.create_repo(space_repo, repo_type="space", space_sdk="docker", exist_ok=True)
api.add_space_variable(space_repo, "IMDB_HF_DATASET", data_repo)
api.add_space_secret(space_repo, "HF_TOKEN", get_token())
api.upload_folder(
    repo_id=space_repo, repo_type="space", folder_path=ROOT,
    allow_patterns=["app.py", "analytics.py", "components.py", "data_loader.py",
                    "visualizations.py", "views/*.py", "assets/*", ".streamlit/config.toml",
                    "requirements.txt", "Dockerfile"],
    commit_message="Deploy dashboard")
api.upload_file(repo_id=space_repo, repo_type="space", path_in_repo="README.md",
                path_or_fileobj=ROOT / "deploy" / "space_README.md")
print("space:", f"https://huggingface.co/spaces/{space_repo}")
