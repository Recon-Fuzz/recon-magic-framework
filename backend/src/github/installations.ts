import { Octokit } from "octokit";
import { getPublicRepoInfo } from "./repos";
import { initNewApp, initOctokit, unauthorizedOctokit } from "./shared";

/**
 * Check if user can access a PRIVATE repo and return an authenticated Octokit.
 * Does NOT check public repos - use this when you've already ruled out public.
 */
export async function getPrivateRepoOctokit(
  user: { id: number; token: string; authenticatedBy: string },
  orgName: string,
  repoName: string
): Promise<Octokit | null> {
  if (user.authenticatedBy === "github") {
    console.log("getPrivateRepoOctokit: github");
    const token = await getAppAccessTokenForRepoIfUserHasAccess(user.token, orgName, repoName);
    return token ? initOctokit(token) : null;
  }

  if (user.authenticatedBy === "apiKeyRead" || user.authenticatedBy === "apiKeyWrite") {
    console.log("getPrivateRepoOctokit: apiKey");
    const hasAccess = await isUserIdCollaboratorPrivate(orgName, repoName, user.id);
    if (!hasAccess) return null;

    const token = await getAppAccessTokenForRepo(orgName, repoName);
    return token ? initOctokit(token) : null;
  }

  return null;
}


export async function verifyUserHasPermissionsForRepo(
  userToken: string,
  orgName: string,
  repoName: string
) {
  try {
    // Never throws, but no token = could be public
    const token = await getAppAccessTokenForRepoIfUserHasAccess(userToken, orgName, repoName);

    if(!token) {
      await getPublicRepoInfo(orgName, repoName); // Thows if it fails, so we just run it and catch it
    }

    return true;
  } catch (e) {
    console.log("Error verifying user has permissions for repo:", e);
    return false;
  }
}

// Auth-aware wrapper: uses token-based check for GitHub OAuth, userId-based check for API keys
export async function checkUserRepoAccess(
  user: { id: number; token: string; authenticatedBy: string },
  orgName: string,
  repoName: string
): Promise<boolean> {
  if (user.authenticatedBy === "github") {
    return verifyUserHasPermissionsForRepo(user.token, orgName, repoName);
  } else if (user.authenticatedBy === "apiKeyRead" || user.authenticatedBy === "apiKeyWrite") {
    return isUserIdCollaborator(orgName, repoName, user.id);
  } else {
    throw new Error(`Unrecognized authenticatedBy: ${user.authenticatedBy}`);
  }
}

//TODO 0XSI
// Globally not efficient
// Implement a new user / gh app installation system in a separate PR

// Given a OrgName and RepoName
// Get the access token necessary for this to work
// NOTE | SECURITY: This should ONLY be used internally, never externally
// Any external use will leak user secrets
export async function getAppAccessTokenForRepo(
  orgName: string,
  repoName: string
) {
  const octokitApp = initNewApp();
  let installRes;
  try {
    // Get install for org
    // We need this for private submodules
    // Note that this may throw! We don't return immediately, we retry for the specific repo
    installRes = await octokitApp.octokit.request(
      "GET /orgs/{org}/installation",
      {
        org: orgName,
      }
    );
  } catch (e) {
    console.log(`ERROR getting the installation for org: ${orgName}:\n`, e);
  }

  // we retry for the specific repo
  if (installRes == null && orgName !== "" && repoName !== "") {
    try {
      // Get install for repo
      installRes = await octokitApp.octokit.request(
        "GET /repos/{owner}/{repo}/installation",
        {
          owner: orgName,
          repo: repoName,
        }
      );
    } catch (e) {
      console.log(`ERROR getting the installation for org: ${orgName} and repo ${repoName}:\n`, e);
      return null;
    }
  }

  if (!installRes) {
    console.log(`Couldn't get install for ${orgName}/${repoName}`);
    return null;
  }

  // If the above doesn't throw then this should be fine
  const {
    data: { token },
  } = await octokitApp.octokit.request(
    "POST /app/installations/{installation_id}/access_tokens",
    {
      installation_id: installRes.data.id,
    }
  );

  return token;
}

// NOTE: SECURITY
// Only use this in workers and internally
// NEVER expose this!!

// Given orgName and repoName
// Throws if no token and no public
// NOTE: THROWS!!!
export async function getCloneUrlAndToken(
  orgName: string,
  repoName: string
): Promise<{ url: string; token: string | null }> {
  const token = await getAppAccessTokenForRepo(orgName, repoName);

  if (!token) {
    const info = await getPublicRepoInfo(orgName, repoName);

    // Public clone URL
    return {
      url: info.clone_url,
      token: null,
    };
  }

  // Token exists, use it for authenticated clone URL
  return {
    url: `https://git:${token}@github.com/${orgName}/${repoName}.git`,
    token,
  };
}

// Return the access token if found
// Return null if not
export async function getAppAccessTokenForRepoIfUserHasAccess(
  userToken: string,
  orgName: string,
  repoName: string
) {
  const allUserRepos = await optimizedGetUserInstalledRepos(userToken);
  const octokitApp = initNewApp();

  // Return only if found
  const found = allUserRepos.find((repo) => {
    return repo.owner.login == orgName && repo.name == repoName;
  });

  if (!found) {
    return null;
  }

  // NOTE: We expect this to never revert as the token should be define for any existing installation
  const {
    data: { token },
  } = await octokitApp.octokit.request(
    "POST /app/installations/{installation_id}/access_tokens",
    {
      installation_id: found.installation_id,
    }
  );

  return token;
}

// Fetch the current commit hash from github
// TODO 0XSI move to gh utils later on
export async function getLatestCommitHash(orgName: string, repoName: string, branch: string, token: string) {
  const octokitApp = new Octokit({
    auth: token
  });

  let commitHash;

  try {
    const response = await octokitApp.request("GET /repos/{owner}/{repo}/commits/{branch}", {
      owner: orgName,
      repo: repoName,
      branch: branch
    });

    commitHash = response.data.sha;
  } catch (error) {
    console.log("Error fetching latest commit hash:", error);
  }

  return commitHash;
}

// NOTE: Basically the main way to verify an install and find it
// We will get installationID from each repo
// So we can use that to directly fetch access token
export async function getUserInstalledRepos(userId: number) {
  // NOTE: From Antonio
  const octokitApp = initNewApp();
  const repos = [];

  for await (const {
    octokit,
    repository,
  } of octokitApp.eachRepository.iterator()) {
    const [{ data: installations }, { data: collaborators }] =
      await Promise.all([
        // NOTE: Not confident on this
        octokit.request("GET /app/installations"), // Get all installations of this key | Pagination
        octokit.request("GET /repos/{owner}/{repo}/collaborators", {
          // NOTE: Maybe for view stuff this is ok, but for more serious stuff I don't trust this
          // NOTE: Owner comes from eachRepository iterator
          owner: repository.owner.login,
          repo: repository.name,
        }),
      ]);

    // do not allow current user access installations of a repository if they are not a collaborator
    if (!collaborators.map((collaborator) => collaborator.id).includes(userId))
      continue;
    const installation = installations.find(
      (installation) => installation.account?.id === userId
    );
    if (!installation) continue;

    // NOTE: This basically grants us access to their repo
    // We need this on the other server to be able to build shit
    // While for OAUTH we would just use their OAUTH token
    // If they are logged in with a session, and that session corresponds to a specific email
    // Then they are logged in
    // const {
    //   data: { token },
    // } = await octokit.request(
    //   "POST /app/installations/{installation_id}/access_tokens",
    //   {
    //     installation_id: installation.id,
    //   }
    // );
    // NOTE: See above to see how token is retrieved

    const project = {
      ...repository,
      installation_id: installation.id,
    };
    repos.push(project);
  }

  return repos;
}


/**
 * Check if user is a collaborator on a PRIVATE repo (no public check).
 */
async function isUserIdCollaboratorPrivate(
  owner: string,
  repo: string,
  userId: number
): Promise<boolean> {
  const octokitApp = initNewApp();

  try {
    const [userResult, orgResult, userResponse] = await Promise.allSettled([
      octokitApp.octokit.request('GET /users/{username}/installation', { username: owner }),
      octokitApp.octokit.request('GET /orgs/{org}/installation', { org: owner }),
      unauthorizedOctokit.request("GET /user/{account_id}", { account_id: Number(userId) })
    ]);

    const installationId =
      userResult.status === 'fulfilled' ? userResult.value.data.id :
      orgResult.status === 'fulfilled' ? orgResult.value.data.id :
      null;

    if (!installationId) return false;

    const userResponseResult = userResponse.status === 'fulfilled' ? userResponse.value : null;
    if (!userResponseResult) return false;

    const username = userResponseResult.data.login;
    const octokit = await octokitApp.getInstallationOctokit(installationId);
    const res = await octokit.request("GET /repos/{owner}/{repo}/collaborators/{username}/permission", { owner, repo, username });

    return res.data.permission !== "none";
  } catch (error: any) {
    console.log("isUserIdCollaboratorPrivate error", error);
    return false;
  }
}

/**
 * Check if user is a collaborator (public repos always return true).
 */
export async function isUserIdCollaborator(
  owner: string,
  repo: string,
  userId: number
): Promise<boolean> {
  // Fast path: public repo
  try {
    const { data } = await unauthorizedOctokit.request("GET /repos/{owner}/{repo}", { owner, repo });
    if (!data.private) return true;
  } catch {}

  return isUserIdCollaboratorPrivate(owner, repo, userId);
}

export async function optimizedGetUserInstalledRepos(userToken: string) {

  const userOctokit = new Octokit({ auth: userToken });
  
  const { data } = await userOctokit.request("GET /user/installations");
  
  const repoPromises = data.installations.map(async (installation) => {
    const { data: repoData } = await userOctokit.request(
      "GET /user/installations/{installation_id}/repositories",
      {
        installation_id: installation.id,
        per_page: 100
      }
    );
    
    return repoData.repositories.map(repository => ({
      ...repository,
      installation_id: installation.id
    }));
  });
  
  const repoArrays = await Promise.all(repoPromises);
  return repoArrays.flat();
}

// NOTE: Currently no real usage
// This should skip pagination so it's slower but more reliable long term
export async function getAllReconInstallations() {
  const octokitApp = initNewApp();

  // NOTE: From Antonio
  const installations = [];
  for await (const { installation } of octokitApp.eachInstallation.iterator()) {
    console.log(installation,"installation");
    installations.push(installation);
  }

  return installations;
}
