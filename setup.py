import subprocess

def clone_repo(repo_url: str):
    """Clone a repository into repo."""
    subprocess.run(["git", "clone", repo_url, "repo"])

def create_and_push_local_gh_repo():
    """Create and push a local GH repo."""
    ## TODO

def update_state_in_api():
    """Update the state in the API."""
    ## TODO

def init_magic_job(repo_url: str):
    """Initialize a magic job."""

    print("Initializing magic job...")
    print(f"Cloning repo from {repo_url}...")
    clone_repo(repo_url)

    ## Create Local GH Repo, remove GH folder and push
    ## So we can push and have it there
    create_and_push_local_gh_repo() ## Cd into repo and get it done

    ## Update State in API
    update_state_in_api()




