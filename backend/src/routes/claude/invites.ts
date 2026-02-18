import { Request, Response } from "express";

import express from "express";
import { onlyLoggedIn, orgCheck } from "../../middleware/auth";
import { fetchClaudeJobById } from "../../db/claudeJobs";
import { inviteUserToRepo } from "../../github/claude-specific";

const router = express.Router();
export default router;

// JOB ID
// USER GH ID

router.post("/", onlyLoggedIn, orgCheck, async (req: Request, res: Response) => {
  const { jobId, githubUsername } = req.body;

  const job = await fetchClaudeJobById(jobId, req.user.userData!.organizationId);

  if (!job) {
    return res.status(404).json({
      message: `Job not found`,
      data: {},
    });
  }

  // Off of the 
  // NOTE: Org + Repo, but org is always the Recon Account, so we don't need that.
  const data = job?.resultData as any;
  if(!data?.repoName || !data?.orgName) {
    return res.status(400).json({
      message: `Repo name not found`,
      data: {},
    });
  }

  if (!githubUsername) {
    return res.status(400).json({
      message: `GitHub username is required`,
      data: {},
    });
  }

  // RepoName available, proceed to invite to the repo
  try {    
    await inviteUserToRepo(data.orgName, data.repoName, githubUsername);

  } catch (error: any) {
    console.error('Failed to invite user to repository:', error);
    return res.status(500).json({
      message: 'Failed to invite user to GitHub repository',
      data: {
        error: error.response?.data || error.message
      },
    });
  }

  return res.json({
    message: `Invited user ${githubUsername} to the repository ${data.repoName}`,
    data: {
      repoName: data.repoName,
      githubUsername: githubUsername,
    },
  });
});