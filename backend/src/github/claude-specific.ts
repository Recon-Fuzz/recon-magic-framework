// NOTE: Make sure to use this EXCLUSIVE for Claude jobs!
import axios from "axios";
import { githubToken } from "../config/config";
import { fetchClaudeJobById } from "../db/claudeJobs";

/**
 * Invite a user, using the Recon Magic Token Auth
 * NOTE: Exclusively for Claude Jobs!
 */
export async function inviteUserToRepo(orgName: string, repoName: string, userHandle: string): Promise<any> {
  const response = await axios.put(
      `https://api.github.com/repos/${orgName}/${repoName}/collaborators/${userHandle}`,
      {
        permission: 'push' // or 'pull', 'triage', 'maintain', 'admin'
      },
      {
        headers: {
          'Accept': 'application/vnd.github.v3+json',
          'Authorization': `token ${githubToken}`,
          'Content-Type': 'application/json'
        }
      }
    );

    return response.data;
}

interface ClaudeJobResultData {
  repoName?: string;
  orgName?: string;
  ref?: string;
  artifacts: {
    name: string;
    format: string;
    content: string;
  }[];
}

/// NOTE: Can throw!
export async function getCommitDiff(claudeJobId: any, organizationId: string): Promise<any> {
  // Get the REPO for the Job 
  // Off of Magic Result get Repo
  // Get the Commit SHA for last one
  // Get the DIFF
  // Return the DIFF
  const claudeJob = await fetchClaudeJobById(claudeJobId, organizationId);
  if(!claudeJob) {
    throw new Error("Claude Job not found");
  }

  const resultData = claudeJob.resultData as unknown as ClaudeJobResultData;

  const repoName = resultData?.repoName;
  const orgName = resultData?.orgName;
  let ref = resultData?.ref;

  if(!repoName || ! orgName) {
    throw new Error("Repo name or org name not found");
  }

  if(!ref) {
    const defaultBranch = await getDefaultBranch(orgName, repoName);
    ref = defaultBranch;
  }

  const lastCommit = await getLastCommit(orgName, repoName, ref);
  const diff = await getRawDiff(orgName, repoName, lastCommit.sha);

  return diff;
}


// INTERNAL

interface GitHubRepo {
  default_branch: string;
  // other fields omitted
}

async function getDefaultBranch(
  owner: string, 
  repo: string
): Promise<string> {
  const { data } = await axios.get<GitHubRepo>(
    `https://api.github.com/repos/${owner}/${repo}`,
    {
      headers: {
        'Authorization': `token ${githubToken}`,
        'Accept': 'application/vnd.github.v3+json'
      }
    }
  );
  
  return data.default_branch;
}

interface Commit {
  sha: string;
  commit: {
    message: string;
    author: {
      name: string;
      email: string;
      date: string;
    };
  };
  html_url: string;
  parents: Array<{ sha: string }>;
}

async function getLastCommit(
  owner: string,
  repo: string,
  branch: string
): Promise<Commit> {
  const { data } = await axios.get<Commit[]>(
    `https://api.github.com/repos/${owner}/${repo}/commits`,
    {
      headers: {
        'Authorization': `token ${githubToken}`,
        'Accept': 'application/vnd.github.v3+json'
      },
      params: {
        sha: branch,
        per_page: 1
      }
    }
  );
  
  return data[0];
}

async function getRawDiff(
  owner: string,
  repo: string,
  sha: string
): Promise<string> {
  const { data } = await axios.get<string>(
    `https://api.github.com/repos/${owner}/${repo}/commits/${sha}`,
    {
      headers: {
        'Authorization': `token ${githubToken}`,
        'Accept': 'application/vnd.github.v3.diff'
      }
    }
  );
  
  return data;
}