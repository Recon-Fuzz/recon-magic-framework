import { initNewApp, initOctokit } from "./shared";

export enum REVIEW_OUTOCOME {
  COMMENT,
  APPROVE,
  BROKEN_PROPERTIES,
}

async function getAuthedOctokit(installationId: string) {
  const octokit = initNewApp();
  const {
    data: { token },
  } = await octokit.octokit.request(
    "POST /app/installations/{installation_id}/access_tokens",
    {
      installation_id: Number(installationId),
    }
  );

  return initOctokit(token);
}

export async function reviewOnGithub(
  orgName: string,
  repoName: string,
  issueId: string,
  body: string,
  installationId: string,
  outcome: REVIEW_OUTOCOME
) {
  try {
    // https://docs.github.com/en/rest/pulls/comments?apiVersion=2022-11-28#create-a-review-comment-for-a-pull-request
    const octokit = await getAuthedOctokit(installationId);

    await octokit.request(
      "POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews",
      {
        owner: orgName,
        repo: repoName,
        pull_number: Number(issueId),
        body: body,
        headers: {
          "X-GitHub-Api-Version": "2022-11-28",
        },
        // NOTE: Can also use "COMMENT" for generic PR comment
        event:
          outcome == REVIEW_OUTOCOME.APPROVE ? "APPROVE" : "REQUEST_CHANGES",
      }
    );
  } catch (e) {
    console.log("reviewOnGithub", e);
  }
}

export async function commentOnGithub(
  orgName: string,
  repoName: string,
  issueId: string,
  body: string,
  installationId: string
): Promise<void> {
  try {
    const octokit = await getAuthedOctokit(installationId);
    await octokit.request(
      "POST /repos/{owner}/{repo}/issues/{issue_number}/comments",
      {
        owner: orgName,
        repo: repoName,
        issue_number: Number(issueId),
        body: body,
        headers: {
          "X-GitHub-Api-Version": "2022-11-28",
        },
      }
    );
  } catch (e) {
    console.log("commentOnGithub error", e);
  }
}
