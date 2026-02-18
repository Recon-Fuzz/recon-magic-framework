import { getCloneUrlAndToken } from "../github/installations";
import { getLatestCommitForRepo } from "../github/repos";

export const getMetaData = async (
  metadata: any,
  orgName: string,
  repoName: string,
  ref: string,
) => {
  let updatedMetadata = metadata;
  let fetchedToken = "";
  try {
    const { token } = await getCloneUrlAndToken(orgName, repoName);
    if (token) {
      fetchedToken = token;
    }
  } catch (error) {
    console.log("no token found", error);
  }
  const latestCommit = await getLatestCommitForRepo(orgName, repoName, ref, fetchedToken || undefined);

  // If we found the latest commit let's add that to the metadata
  if (latestCommit) {
    updatedMetadata = {
      commit: latestCommit, // The commit at which this job is run
      ...updatedMetadata,
    };
  }
  return updatedMetadata;
};
