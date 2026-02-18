import { getLatestCommitForRepo } from "../github/repos";

//TODO 0XSI
// A lot of unused fn

// Or if the repo is their own
// User has access, if they belong to an org that has access

// TODO: Add Sharing

// A user can access a Repo if
// They are the Owner of the Repo (same name)  - Write Access
// They are part of an Org and the Org has access to the repo  - Write Access
// The Repo is public - Read Access

// Given orgName and userId
// Check if the user has a pre-installed token that has access to the repo
// if they do return it
async function getOrCheckUserInstallToken(orgName: string, userId: string) {
  // Verify Org matches logged in user `login` matches orgName
}

// TODO: Given Org Name, get the Org Token
async function getOrCheckOrgInstallToken(orgName: string, orgId: string) {}

// TODO: Prob check if user is in org via DB
async function isUserInOrg(orgName: string, consumingUserId: string) {}

// TODO: Sharing is disabled for now
async function isRepoShared(
  orgName: string,
  repoName: string,
  consumingUserId: string
) {}

// NOTE: Given org, repo and ref, gets the hash
// NOTE: Will return null on failure
export async function getPublicOpenRepoHash(
  orgName: string,
  repoName: string,
  ref: string
): Promise<null | string> {
  try {
    return await getLatestCommitForRepo(orgName, repoName, ref);
  } catch {
    return null;
  }
}
