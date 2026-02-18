import { Request, Response } from "express";

import express from "express";
import { createJob } from "../db/jobs";
import { getOrgByName, getOrganization } from "../db/organizations";
import { getUserInfo } from "../db/users";
import { BILLING_STATUS, WEBHOOK_TYPE } from "@prisma/client";
import {
  createNewWebhookJob,
  fetchLastFivewebhookJobs,
} from "../db/webhookJob";
import { onlyLoggedIn, orgCheck, requireProOrg } from "../middleware/auth";
import { commentOnGithub } from "../github/comment";
import { fetchCampaignsByWebhookData } from "../db/campaigns";
import { makeJobFromRecipe } from "../recipes";
import {
  enableRunsOnCommit,
  jsonWebTokenSecretRunner,
  linkPrefix,
  githubWebhookSecret
} from "../config/config";
import { getMetaData } from "../utils/metadata";
import { createOrUpdateGHData, getGHdataByJobId } from "../db/githubData";
import jwt from "jsonwebtoken";
import prisma from "../db/client";
import { Fuzzer, generateJobMD } from "@recon-fuzz/log-parser";
import { getLogs } from "../utils";
import { getSignedUrl } from "../aws/cloudfront";
import { getAlertById } from "../db/alerts";
import { sendMessage } from "../utils/telegram";
import { Webhooks } from "@octokit/webhooks";

// Extend Express Request to include rawBody for webhook signature verification
declare global {
  namespace Express {
    interface Request {
      rawBody?: Buffer;
    }
  }
}

const router = express.Router();
export default router;

// Add JSON parsing middleware with raw body capture for GitHub signature verification
router.use(
  express.json({
    verify: (req: any, res, buf, encoding) => {
      // Store raw body for GitHub signature verification
      req.rawBody = buf;
    },
  })
);

// Initialize GitHub Webhooks for signature verification (only if secret is configured)
const webhooks = githubWebhookSecret ? new Webhooks({
  secret: githubWebhookSecret
}) : null;

// refs/heads/add -> Push to PR
// action: opened -> Open PR

interface InstallationData {
  id: number;
}

// PUSH TO BRANCH!!!
interface GithubCommitWebhook {
  ref?: string; // 'refs/heads/add'
  // If it's valid these will always be there
  before: string; // '4c83c869b4d5c03321a309797b139e9c73de6902',
  after: string; // '4526dd6fd05272e87ee9ba9b62fc3b56fb4c3b56',
  repository: {
    id: number; // 761909186; // This may be useful but we don't use it
    node_id: string;
    name: string;
    full_name: string; // 'GalloDaSballo/recon-demo-3', // ORG/REPO@after is the fully qualified URL
  };

  sender: {
    id: number; // 13383782;
  };
  // Given USER -> OrgID
  // Verify Pro
  // Verify Valid ID
  // Add to their org
  // Acceptable for now

  installation: InstallationData;
}

interface GithubPRData {
  ref: string; //
  repo: {
    name: string;
    full_name: string;
  };

  installation: InstallationData;
}

type Head = GithubPRData;
type Base = GithubPRData;

interface GithubPRWebhok {
  number: number;
  ref: string;
  pull_request: {
    id: string;
    head: Head;
    base: Base;
  };
  repository: {
    full_name: string;
  }
  installation: InstallationData;
}

// Synch PR
interface GithubSynchedPRWebhook extends GithubPRWebhok {
  action: "synchronize";
}

// Open PR
interface GithubOpenPRWebhook extends GithubPRWebhok {
  action: "opened";
}

function getWebhookType(body: any): WEBHOOK_TYPE | undefined {
  // Body includes refs/heads
  // Legacy Git stuff = Commit Push
  if (body?.ref?.includes("refs/heads")) {
    return WEBHOOK_TYPE.COMMIT;
  }

  // Event is Pull and Synchronize = PR Update
  if (body?.action === "synchronize" && body?.pull_request?.id) {
    return WEBHOOK_TYPE.PR_UPDATE;
  }

  // Action = Opened and The field Pull Request exists = PR Created
  if (body?.action === "opened" && body?.pull_request?.id) {
    return WEBHOOK_TYPE.PR_CREATION;
  }

  if (body?.action === "runner_end_run") {
    return WEBHOOK_TYPE.RUNNER_END_RUN;
  }

  if (body?.action === "broken_property_alert") {
    return WEBHOOK_TYPE.BROKEN_PROPERTY_ALERT;
  }

  if (body?.action === "coverage_snapshot") {
    return WEBHOOK_TYPE.COVERAGE_SNAPSHOT;
  }

  return undefined;
}

// TODO: This logic is a bit brittle
// The proper logic is to replace the name with "" to remove it
// That way you should always be able to separate the ORG and BRANCH
function getOrgAndRepo(full_name: string, name: string): string[] {
  // Expected: [orgName: string, repoName: string]
  const orgName = full_name.replace(`/${name}`, "");

  return [orgName, name];
}

/// Given userId, returns
async function getOrgIdIfValid(userId: string): Promise<string | undefined> {
  const userInfo = await getUserInfo(String(userId));

  if (!userInfo) {
    console.log("Not ran webhooks due to user not found");
    return;
  }

  const orgInfo = await getOrganization(userInfo?.organizationId);

  if (!orgInfo?.billingStatus) {
    console.log("Not ran webhooks due to org not found");
    return;
  }

  if (orgInfo.billingStatus != BILLING_STATUS.PAID) {
    console.log("Not ran webhooks due to unpaid");
    return;
  }

  return orgInfo.id;
}

// Handle Commit Push Webhook
async function processCommitPushWebhook(
  organizationId: string,
  orgName: string,
  repoName: string,
  ref: string
): Promise<void> {
  if (organizationId == "") {
    try {
      const orgInfo = await getOrgByName(orgName);
      organizationId = orgInfo.id;
    } catch {
      // If we can't find the org we cannot create a job
      console.log("Error: org not found by name");
      return;
    }
  }
  // The notification
  const notification = await createNewWebhookJob(
    organizationId,
    WEBHOOK_TYPE.COMMIT,
    orgName,
    repoName,
    // copiedBody.after // NOTE: This doesn't work with git clone, needs changes to runner
    ref
  );

  console.log("Created webhook with id", notification.id);
}

function getLinkToJob(jobId: string) {
  if (linkPrefix) {
    return `${linkPrefix}${jobId}`;
  }

  // Default to Prod
  return `https://getrecon.xyz/dashboard/jobs/${jobId}`;
}

interface JobInfo {
  recipeName: string;
  jobId: string;
  timestamp?: string;
}

function makeReconMessage(campaignName: string, jobInfos: JobInfo[]): string {
  let message = `## Recon Campaign Started ${campaignName}`;

  jobInfos.forEach((jobInfo) => {
    message += `\n`;
    message += `- Recipe: ${jobInfo.recipeName} | Job URL: ${getLinkToJob(
      jobInfo.jobId
    )}`;
  });

  return message;
}

function getCommitPushJobData(body: GithubCommitWebhook) {
  const orgAndRepo = getOrgAndRepo(
    body.repository.full_name,
    body.repository.name
  );

  const orgName = orgAndRepo[0];
  const repoName = orgAndRepo[1];
  const branchName = body?.ref?.split("refs/heads/")[1];

  return {
    orgName,
    repoName,
    ref: branchName,
    installationId: String(body.installation.id),
  };
}

function getPRJobData(body: GithubPRWebhok) {
  const full_name = body.repository.full_name;
  const orgName = full_name.split("/")[0];
  const repoName = full_name.split("/")[1];
  let branchName = body.pull_request?.head?.ref;
  if (!branchName) {
    branchName = body?.ref?.split("refs/heads/")[1];
  }

  return {
    orgName,
    repoName,
    ref: branchName,
    installationId: String(body.installation.id),
    number: String(body.number),
  };
}
function getPRMessageData(body: GithubPRWebhok) {
  const full_name = body.repository.full_name;
  const orgName = full_name.split("/")[0];
  const repoName = full_name.split("/")[1];
  let branchName = body.pull_request?.head?.ref;
  if (!branchName) {
    branchName = body?.ref?.split("refs/heads/")[1];
  }

  return {
    orgName,
    repoName,
    ref: branchName,
    installationId: String(body.installation.id),
    number: String(body.number),
  };
}

// Check and Run Campaign -> Return what was queued
// With Comment, true | false -> Separate comment Function

// Each campaign will generate a run, since each repo can have more than one
// We have to return a list of them
interface CampaignRuns {
  campaign: {
    displayName: string;
    id: string;
    authorizedComments: boolean;
  };
  runs: JobInfo[];
}

async function checkAndRunCampaign(
  orgName: string,
  repoName: string,
  ref: string,
  organizationId: string,
  initiator: number
): Promise<CampaignRuns[]> {
  // Find all campaigns given the info
  const campaigns = await fetchCampaignsByWebhookData(
    orgName,
    repoName,
    ref,
    initiator
  );

  console.log("campaigns for org, repo, branch", campaigns);

  const campaignRuns = await Promise.all(
    campaigns.map(async (campaign) => {
      const jobInfos = await Promise.all(
        campaign.recipes.map(async (recipe) => {
          const asJobInput = makeJobFromRecipe(
            {
              orgName,
              repoName,
              ref,
            },
            recipe
          );

          let suppliedMetadata: any = {
            startedBy: campaign.organizationId,
            method: "webhook",
          };

          let metadata;
          try {
            metadata = await getMetaData(
              suppliedMetadata,
              orgName,
              repoName,
              ref
            );
          } catch {
            console.log("Job: couldn't create access token");
          }

          // TODO: Need better re-usability
          const createdJob = await createJob(
            campaign.organizationId, /// @audit NOTE: This goes to the Webhook Recipient, but the recipe logic adds to recipe
            asJobInput.orgName,
            asJobInput.repoName,
            asJobInput.ref,
            asJobInput.fuzzer,
            asJobInput.label ? `Campaign - ${asJobInput.label}` : "Campaign",
            {
              fuzzerArgs: asJobInput.fuzzerArgs,
              directory: asJobInput.directory,
              duration: asJobInput.duration,
              preprocess: asJobInput.preprocess,
              arbitraryCommand: asJobInput.arbitraryCommand,
              metadata: metadata ? metadata : suppliedMetadata, // there will always be metadata in this case
            },
            recipe.id
          );

          return {
            jobId: createdJob.id,
            timestamp: createdJob.createdAt.toISOString(),
            recipeName: recipe.displayName,
          };
        })
      );

      // Return the formatted data
      return {
        campaign: {
          displayName: campaign.displayName || "",
          id: campaign.id,
          authorizedComments: campaign.comments, // True if we are allowed to comment
        },
        runs: jobInfos,
      };
    })
  );

  return campaignRuns;
}

// Handle Campaign

async function handleCampaignForPR(
  body: GithubPRWebhok,
  orgId: string,
  initiator: number
) {
  // Head is where we run the code
  const { orgName, repoName, ref } = getPRJobData(body);

  // Handle the case where an outside collaborator triggered the campaign
  if (orgId == "") {
    try {
      // 1. Check if we have an org with the given orgName
      const orgInfo = await getOrgByName(orgName);
      console.log("org info:", orgInfo);
      orgId = orgInfo.id;
    } catch {
      // If we can't find the org we cannot create a job
      console.log(`Error: org not found by name as a standalone org: ${orgName}`);
    }
  }
  if (!orgId || orgId == "") {
    // If not found, we need to check if there is a campaign for this org
    const found = await prisma.campaign.findFirst({
      where: {
        orgNames : {
          has: orgName,
        },
        organization: {
          billingStatus: 'PAID',
        },
      },
      include: {
        organization: true,
      },
    });
    if (!found) {
      console.log(`No campains found matching this org: ${orgName} \n Canceling.`);
      return;
    }
    console.log(`found the orgId. The orgName ${orgName} is associated with orgId ${found.organization.id}`);
    // Possible that we want to launch a campaign for org X  but it doesn't exist as an org
    // Instead, org Y has the campaign for org X
    orgId = found.organization.id;
  }

  // Create jobs here if available
  const runs = await checkAndRunCampaign(
    orgName,
    repoName,
    ref,
    orgId,
    initiator
  );

  console.log("Runs from checkAndRunCampaign", runs.length);

  // Base is destination I think
  const {
    orgName: orgNameMsg,
    repoName: repoNameMsg,
    installationId: installationIdMsg,
    number,
  } = getPRMessageData(body);

  // Send messages here if necessary
  await Promise.all(
    runs.map(async (run: CampaignRuns) => {
      const latestJob = run.runs.sort(
        (a, b) =>
          new Date(b.timestamp!).getTime() - new Date(a.timestamp!).getTime()
      )[0];
      try {
        await createOrUpdateGHData(
          run.campaign.id, // campain ID
          orgNameMsg,
          repoNameMsg,
          ref, // PR
          parseInt(number),
          parseInt(installationIdMsg),
          latestJob.jobId
        );
      } catch (err) {
        console.log("Issue creating github data", err);
      }
      if (run.campaign.authorizedComments === false) {
        return;
      } else {
        return await commentOnGithub(
          orgNameMsg,
          repoNameMsg,
          String(number),
          makeReconMessage(run.campaign.displayName || "", run.runs),
          String(installationIdMsg)
        );
      }
    })
  );
}

// Campaign
// Create a Job from Data + Recipe
// Comment on Issue ID of Customer
// DONE

// NOTE: Highly likely these webhooks can be spammed
// TODO: Add Secret or smth
router.post("/", async (req: Request, res: Response) => {
  // TODO: Handle installation case
  //gist.github.com/GalloDaSballo/cca5732ebd3416bc82d8078a25d6c6fb

  console.log("Webhooks hit");
  // console.log(req.body)

  const webhookType = getWebhookType(req.body);
  console.log("Webook type received:", webhookType);
  // Early end
  if (!webhookType) {
    console.log("Webhook type not supported, body passed: ", req.body);
    return res.json({});
  }

  if (webhookType === WEBHOOK_TYPE.BROKEN_PROPERTY_ALERT) {
    console.log("HIT BROKEN PROPERTY ALERT");
    const bearer = req.headers.authorization;
    if (!bearer) {
      res.status(401);
      return res.json({ message: "Unauthorized" });
    }
    const valid = jwt.verify(bearer, jsonWebTokenSecretRunner);
    if (!valid) {
      res.status(401);
      return res.json({ message: "Invalid token" });
    }
    const { jobId, alertId, brokenProperty, sequence } = req.body;
    const alert = await getAlertById(alertId);
    if (!alert) {
      res.status(404);
      return res.json({ message: "Alert not found" });
    }

    if (alert.webhookUrl) {
      const { webhookUrl } = alert;

      console.log("Alert found ... Calling Alert Webhook ....")
      const response = await fetch(webhookUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          alertId,
          jobId,
          brokenProperty,
          sequence,
        }),
      });
      console.log("Response from calling webhook sent in alert", response);
    }

    if (alert.telegramChatId && alert.telegramHandle) {
      const message = `⚠️⚠️⚠️ \n Broken Property: ${brokenProperty} \n Job link: ${linkPrefix}${jobId} \n  `;
      await sendMessage(message, alert.telegramChatId);
    }
    res.status(200);
    return res.json({});
  }

  if (webhookType === WEBHOOK_TYPE.COVERAGE_SNAPSHOT) {
    console.log("HIT COVERAGE_SNAPSHOT");
    const bearer = req.headers.authorization;
    if (!bearer) {
      res.status(401);
      return res.json({ message: "Unauthorized" });
    }

    try {
      const valid = jwt.verify(bearer, jsonWebTokenSecretRunner);
      if (!valid) {
        res.status(401);
        return res.json({ message: "Invalid token" });
      }
    } catch (jwtError) {
      console.error("[coverage] JWT verification error:", jwtError);
      res.status(401);
      return res.json({ message: "Invalid token" });
    }

    const { jobId, coveragePercent, perFile, timestamp } = req.body;

    try {
      const job = await prisma.job.findUnique({ where: { id: jobId } });
      if (!job) {
        res.status(404);
        return res.json({ message: "Job not found" });
      }

      // Reservoir sampling: keep initial, up to 3 evenly-spread samples, and latest
      const jobStartTime = job.createdAt.getTime();
      const snapshotTime = new Date(timestamp).getTime();
      const elapsed = snapshotTime - jobStartTime;

      const snapshot = {
        timestamp,
        coveragePercent,
        perFile,
        elapsed, // ms since job start
      };

      // Initialize or retrieve existing reservoir
      let reservoir: {
        initial: typeof snapshot | null;
        samples: (typeof snapshot)[];
        latest: typeof snapshot | null;
      };

      try {
        const existingData = job.coverageData as any;

        // Check if it's already in reservoir format
        if (existingData && typeof existingData === 'object' && 'initial' in existingData) {
          reservoir = existingData;
        } else {
          // Initialize new reservoir (handles null or legacy array format)
          reservoir = {
            initial: null,
            samples: [],
            latest: null,
          };
        }
      } catch (parseError) {
        console.error(`[coverage] Error parsing existing coverage data for job ${jobId}, initializing fresh:`, parseError);
        reservoir = {
          initial: null,
          samples: [],
          latest: null,
        };
      }

      // First snapshot becomes initial
      if (!reservoir.initial) {
        reservoir.initial = snapshot;
        reservoir.latest = snapshot;
      } else {
        // Always update latest
        reservoir.latest = snapshot;

        // Manage middle samples (up to 3, evenly distributed)
        try {
          if (reservoir.samples.length < 3) {
            // Still filling up - just add the sample
            reservoir.samples.push(snapshot);
          } else {
            // Have 3+ samples: re-select to maintain even distribution
            // Target positions: 25%, 50%, 75% of elapsed time
            const candidates = [...reservoir.samples, snapshot];
            const totalElapsed = elapsed;
            const targets = [0.25, 0.5, 0.75];
            const selected: (typeof snapshot)[] = [];
            const usedIndices = new Set<number>();

            for (const target of targets) {
              const targetTime = totalElapsed * target;
              let bestIdx = 0;
              let bestDiff = Infinity;

              for (let i = 0; i < candidates.length; i++) {
                if (usedIndices.has(i)) continue;
                const diff = Math.abs(candidates[i].elapsed - targetTime);
                if (diff < bestDiff) {
                  bestDiff = diff;
                  bestIdx = i;
                }
              }

              usedIndices.add(bestIdx);
              selected.push(candidates[bestIdx]);
            }

            reservoir.samples = selected;
          }
        } catch (samplingError) {
          console.error(`[coverage] Error during sampling for job ${jobId}:`, samplingError);
          // Keep existing samples on error
        }
      }

      await prisma.job.update({
        where: { id: jobId },
        data: { coverageData: reservoir },
      });

      const sampleCount = reservoir.samples.length;
      console.log(`[coverage] Stored snapshot for job ${jobId}: ${coveragePercent.toFixed(2)}% (reservoir: initial + ${sampleCount} samples + latest)`);
      res.status(200);
      return res.json({});
    } catch (error) {
      console.error(`[coverage] Error storing snapshot for job ${jobId}:`, error);
      res.status(500);
      return res.json({ message: "Error storing coverage snapshot" });
    }
  }

  if (webhookType === WEBHOOK_TYPE.RUNNER_END_RUN) {
    console.log("Received webhook from runner, end of run");
    const bearer = req.headers.authorization;
    if (!bearer) {
      res.status(401);
      return res.json({ message: "Unauthorized" });
    }
    const valid = jwt.verify(bearer, jsonWebTokenSecretRunner);
    if (!valid) {
      res.status(401);
      return res.json({ message: "Invalid token" });
    }
    const ghData = await getGHdataByJobId(req.body.jobId);
    if (!ghData) {
      console.log("No GH data found for job");
      res.status(404);
      return res.json({});
    }
    if (ghData.campaign.comments) {
      if (!req.body.jobId) {
        throw new Error("No job ID provided");
      }
      const job = await prisma.job.findUnique({
        where: {
          id: req.body.jobId,
        },
      });
      if (!job) {
        throw new Error("Job not found");
      }
      if (!job.logsUrl) {
        console.log("no logs available yet");
        return;
      }
      const { logs } = await getLogs(getSignedUrl(job.logsUrl));
      if (!logs) {
        console.log("no logs");
      }
      // Handle if customer disable comments
      const jobMd = generateJobMD(
        job.fuzzer as Fuzzer,
        logs,
        job.label || `${job.orgName}/${job.repoName}`
      );
      const genericText = `# Recon Job Completed\n\n [Job link](${getLinkToJob(
        req.body.jobId
      )})`;
      await commentOnGithub(
        ghData.orgName,
        ghData.repoName,
        ghData.issueId!.toString(),
        `${genericText}\n${jobMd}`,
        ghData.installationId!.toString()
      );
      res.status(200);
      return res.json({});
    } else {
      console.log("Comments are disabled for this campaign");
      res.status(200);
      return res.json({});
    }
  }

  // GitHub Webhook Secret Validation
  const signature = req.headers["x-hub-signature-256"] as string;

  if(githubWebhookSecret && !signature) {
    console.log("Unauthorized: No signature provided, but secret is configured");
    res.status(401).send("Unauthorized");
    return;
  }

  // Verify GitHub webhook signature if secret is configured
  if(githubWebhookSecret && webhooks && req.rawBody) {
    try {
      const isValid = await webhooks.verify(req.rawBody.toString('utf-8'), signature);
      if (!isValid) {
        console.log("Unauthorized: Invalid GitHub webhook signature");
        res.status(401).send("Unauthorized");
        return;
      }
      console.log("GitHub webhook signature verified successfully");
    } catch (error) {
      console.log("Error verifying GitHub webhook signature:", error);
      res.status(401).send("Unauthorized");
      return;
    }
  }



  // Get the user from the request
  const userId = req.body.sender.id;

  // We do not return if the orgId is undefined, because it will be for users outside Recon
  // But we confirm the sender is allowed to initiate jobs on this PR inside `fetchCampaignsByWebhookData`
  let orgId = await getOrgIdIfValid(String(userId));

  if (!orgId) {
    orgId = "";
    console.log("Outside collaborator: Sender not on Recon");
  }
  // PR UPDATE
  if (webhookType === WEBHOOK_TYPE.COMMIT) {
    console.log("Identified a COMMIT to a Repo");

    const { orgName, repoName, ref } = getCommitPushJobData(req.body);
    if (!ref) {
      return;
    }

    await processCommitPushWebhook(orgId, orgName, repoName, ref);

    if (enableRunsOnCommit) {
      console.log("In enableRunsOnCommit");
      // NOTE: Disabled by default because we otherwise would queue on both synch and push
      const runs = await checkAndRunCampaign(
        orgName,
        repoName,
        ref,
        orgId,
        userId
      );
      console.log("WEBHOOK_TYPE.COMMIT, runs", runs);
    }
    res.status(200);
    return res.json({});
  }

  // TODO: Other 2 types of webhooks
  if (webhookType === WEBHOOK_TYPE.PR_CREATION) {
    // Get user, org, etc..
    console.log("Identified a PR_CREATION to a Repo");

    await handleCampaignForPR(req.body, orgId, userId);
    res.status(200);
    return res.json({});
  }

  if (webhookType === WEBHOOK_TYPE.PR_UPDATE) {
    // Get user, org, etc..
    console.log("Identified a PR_UPDATE to a Repo");

    await handleCampaignForPR(req.body, orgId, userId);
    res.status(200);
    return res.json({});
  }

  // DEFAULT
  console.log("Webhook Default");
  return res.json({});
});

router.get(
  "/",
  onlyLoggedIn,
  requireProOrg,
  orgCheck,
  async (req: Request, res: Response) => {
    const webhookJobs = await fetchLastFivewebhookJobs(
      req.user.userData!.organizationId
    );

    return res.json({
      data: webhookJobs,
      message: "Last five webhooks for the Org",
    });
  }
);

// TODO: Add a way to fetch for a specific repo / org

// TODO: Add a way to consume the webhook and delete it
