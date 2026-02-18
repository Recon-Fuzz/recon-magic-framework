import express from "express";
import { Request, Response } from "express";

import { requireSuperAdmin } from "../../middleware/auth";
import {
  getAllReconInstallations,
} from "../../github/installations";
import { getLatestCommitForRepo } from "../../github/repos";
import {
  getAllOrgs,
  giveProToOrg,
  giveTrialOrg,
  removeProFromOrg,
  setMinutesToOrg,
} from "../../db/organizations";
import { deleteUserAndOrg, getAllUsers } from "../../db/users";

import superClaudeJobsRoutes from "./claude/jobs";
import superStatsRoutes from "./stats";

import superAbiRoutes from "./abi";
import superAbiJobsRoutes from "./abiJobs";
import superCampaignRoutes from "./campaigns";
import ghRoutes from "./gh";
import govFuzzingRoutes from "./governanceFuzzing";
import superJobsRoutes from "./jobs";
import superListenersRoutes from "./listeners";
import superMonitoringRoutes from "./monitorings";
import superOrganizationRoutes from "./organizations";
import superOrgInviteRoutes from "./orgInvites";
import superApiKeyRoutes from "./apiKey";
import superMagicCreditsRoutes from "./magicCredits";

import pingRoutes from "./ping";
import recipesRoutes from "./recipes";
import recurringRoutes from "./recurring";
import servicesRoutes from "./services";
import shareRoutes from "./shares";
import webhookRoutes from "./webhooks";
import systemSettingsRoutes from "./systemSettings";

import { commentOnGithub } from "../../github/comment";


const router = express.Router();
export default router;

// TODO: Can we just add require here to always get the require super admin?

router.use("/claude/jobs", superClaudeJobsRoutes);
router.use("/stats", superStatsRoutes);
router.use("/jobs", superJobsRoutes);
router.use("/monitorings", superMonitoringRoutes);
router.use("/abi", superAbiRoutes);
router.use("/abiJobs", superAbiJobsRoutes);
router.use("/apiKey", superApiKeyRoutes);
router.use("/campaigns", superCampaignRoutes);
router.use("/organizations", superOrganizationRoutes);
router.use("/orgInvites", superOrgInviteRoutes);
router.use("/magic-credits", superMagicCreditsRoutes);
router.use("/gh", ghRoutes);
router.use("/listeners", superListenersRoutes);
router.use("/govFuzzing", govFuzzingRoutes);
router.use("/recipes", recipesRoutes);
router.use("/recurring", recurringRoutes);
router.use("/services", servicesRoutes);
router.use("/shares", shareRoutes);
router.use("/webhooks", webhookRoutes);
router.use("/ping", pingRoutes);
router.use("/system", systemSettingsRoutes);

router.delete(
  "/user",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { userGithubId } = req.body;
    const data = await deleteUserAndOrg(userGithubId);

    // NOTE: You cannot delete the org because it will have jobs
    // Deleting org is more complex
    return res.json({
      message: "Deleted both user and the org they belong to",
      data,
    });
  }
);

router.post("/trial/", requireSuperAdmin, async (req: Request, res: Response) => {
  const { orgId } = req.body;

  const data = await giveTrialOrg(orgId);

  return res.json({ message: "trial", data });
});

router.post("/pro/", requireSuperAdmin, async (req: Request, res: Response) => {
  const { orgId } = req.body;

  const data = await giveProToOrg(orgId);

  return res.json({ message: "pro", data });
});
router.post(
  "/cancel/",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { orgId } = req.body;

    const data = await removeProFromOrg(orgId);

    return res.json({ message: "Removed", data });
  }
);

router.post(
  "/minutes/",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { orgId, amount } = req.body;

    const data = await setMinutesToOrg(orgId, amount);

    return res.json({ message: `added ${amount} of minutes`, data });
  }
);

router.get("/orgs", requireSuperAdmin, async (req: Request, res: Response) => {
  const data = await getAllOrgs();

  return res.json({ message: "All orgs", data });
});

router.get("/users", requireSuperAdmin, async (req: Request, res: Response) => {
  const data = await getAllUsers();

  return res.json({ message: "All Users", data });
});

router.get(
  "/commit/:orgName/:repoName/:branch",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { orgName, repoName, branch } = req.params;

    const hash = await getLatestCommitForRepo(orgName, repoName, branch);

    return res.json({ message: "Hash of Public Repo", data: hash });
  }
);

// Returns all Installations
// NOTE: This is interesting because we can prob use just /installations to retrieve them
router.get(
  "/installations/",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const installations = await getAllReconInstallations();

    return res.json({ message: "All installations", data: installations });
  }
);


/// NOTE: Quick and dirty way to test for the ability to comment
router.post(
  "/comment/",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { orgName, repoName, issueId, body, installationId } = req.body;

    await commentOnGithub(orgName, repoName, issueId, body, installationId);

    return res.json({
      message: "Sent Comment to arbitrary destination",
      data: {},
    });
  }
);
