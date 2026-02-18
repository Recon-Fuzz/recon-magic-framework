import { initOctokit, unauthorizedOctokit } from "./shared";

// NOTE: Doesn't work for private repo
// NOTE: Throws!
// If not found it will throw above
// Throwing desired
export async function getLatestCommitForRepo(
  orgName: string,
  repoName: string,
  branch: string,
  token?: string
): Promise<string> {
  const octokit = initOctokit(token);

  // Request the sha
  const {
    data: { sha },
  } = await octokit.request("GET /repos/{owner}/{repo}/commits/{ref}", {
    owner: orgName,
    repo: repoName,
    ref: branch,
    headers: {
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });

  return sha;
}

// If not found it will throw above
// Throwing desired
export async function getPublicRepoInfo(orgName: string, repoName: string) {
  const { data } = await unauthorizedOctokit.request(
    "GET /repos/{owner}/{repo}",
    {
      owner: orgName,
      repo: repoName,
    }
  );

  return data;
}

export async function fetchAllSolidityFiles(
  orgName: string,
  repoName: string,
  branch: string,
  token?: string
): Promise<Array<{ path: string; sha: string; size: number; url: string }>> {
  const octokit = initOctokit(token);
  
  // Get the latest commit SHA for the branch
  const latestCommitSha = await getLatestCommitForRepo(orgName, repoName, branch, token);

  // Fetch the tree recursively
  const { data: tree } = await octokit.request(
    "GET /repos/{owner}/{repo}/git/trees/{tree_sha}",
    {
      owner: orgName,
      repo: repoName,
      tree_sha: latestCommitSha,
      recursive: "true",
      headers: {
        "X-GitHub-Api-Version": "2022-11-28",
      },
    }
  );

  // Filter for Solidity files (.sol extension)
  const solidityFiles = tree.tree
    .filter((item) =>
      item.type === "blob" &&
      item.path &&
      item.path.endsWith(".sol")
    )
    // TS bs
    .map((item) => ({
      path: item.path!,
      sha: item.sha!,
      size: item.size || 0,
      url: item.url!,
    }));

  return solidityFiles;
}
