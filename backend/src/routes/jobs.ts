import { Request, Response } from "express";
import express from "express";
import { createHash } from "crypto";
import { FUZZER } from "@prisma/client";
import {
  onlyLoggedIn,
  orgCheck,
  requireProOrg,
  onlyRunner,
  requireListener,
} from "../middleware/auth";
import { sanitizeInput } from "../middleware/sanitizer";
import {
  createdJobFromPrevJob,
  createJob,
  fetchOneJob,
  getAllEndedOrgJobs,
  getAllErroredOrgJobs,
  getAllOrgJobs,
  getAllRunningOrgJobs,
  getOneOrgJob,
  stopJob,
  updateJobLabel,
} from "../db/jobs";
import { sanitizePreprocess } from "../sanitizePreprocess";
import { unsafeFetchClaudeJobById } from "../db/claudeJobs";
import {
  createBrokenProperty,
  getBrokenPropertiesForJob,
  updateJobRunData,
} from "../db/brokenProperty";
import { getMetaData } from "../utils/metadata";
import { getCloneUrlAndToken, checkUserRepoAccess } from "../github/installations";
import { initOctokit } from "../github/shared";

const router = express.Router();
export default router;
/**
 * TODO: PORT OVER SUPER STUFF
 */

// Create a Job
// TODO: Authentication of Repo
// TODO: Figure out if this would work
// TODO: Maybe rename away from "Job"

// Middleware to extract and validate fuzzer type from URL parameter
function extractFuzzerFromUrl(req: Request, res: Response, next: any) {
  const fuzzerTypeString = req.params.fuzzerType.toUpperCase();

  if (!Object.values(FUZZER).includes(fuzzerTypeString as FUZZER)) {
    res.status(400);
    return res.json({
      message: `Invalid fuzzer type: ${req.params.fuzzerType}`,
      data: {},
    });
  }

  // Store validated fuzzer type in req for handler to use
  (req as any).validatedFuzzerType = fuzzerTypeString as FUZZER;
  (req as any).metadataMethod = "website";
  next();
}

// Middleware to extract and validate fuzzer type from request body (for listener)
function extractFuzzerFromBody(req: Request, res: Response, next: any) {
  const fuzzerType = req.body.fuzzerType || "ECHIDNA"; // Default to ECHIDNA for backwards compatibility
  const fuzzerTypeString = fuzzerType.toUpperCase();

  if (!Object.values(FUZZER).includes(fuzzerTypeString as FUZZER)) {
    res.status(400);
    return res.json({
      message: `Invalid fuzzer type: ${fuzzerType}`,
      data: {},
    });
  }

  // Store validated fuzzer type in req for handler to use
  (req as any).validatedFuzzerType = fuzzerTypeString as FUZZER;
  (req as any).metadataMethod = "listener";
  next();
}

// UUID validation helper
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Shared handler function for all job creation
async function createJobHandler(req: Request, res: Response) {
  const fuzzerType = (req as any).validatedFuzzerType as FUZZER;
  const metadataMethod = (req as any).metadataMethod as string;

  // Get params from Body
  const {
    orgName,
    repoName,
    ref,
    directory,
    duration,
    fuzzerArgs,
    preprocess,
    label,
    recipeId,
    sourceJobId
  } = req.body;

  // Get user ID - for listener, fallback to empty string
  const userId = req.user.id ? req.user.id.toString() : (req.user.userData?.id ? req.user.userData.id.toString() : "");

  // Verify user has access to repo (handles both GitHub OAuth and API key auth)
  const hasAccess = await checkUserRepoAccess(req.user, orgName, repoName);
  if(!hasAccess) {
   return res.status(401).json({
     message: "You do not have access to this repo",
   });
  }

  // Composition fields (set if sourceJobId is provided)
  // sourceJobId can be a Pro Job (Job table) or Magic Job (ClaudeJob table)
  let forkedFromId: string | undefined;
  let forkedFromType: "Job" | "ClaudeJob" | undefined;
  let originalOrgName: string | undefined;
  let originalRepoName: string | undefined;

  if (sourceJobId) {
    // Validate sourceJobId format
    if (!UUID_REGEX.test(sourceJobId)) {
      return res.status(400).json({ message: "Invalid sourceJobId format" });
    }

    // Try fetching from both tables (Pro Job first, then Magic Job)
    let proJob = null;
    try {
      proJob = await fetchOneJob(sourceJobId);
    } catch {
      // Job not found, will try ClaudeJob
    }
    const magicJob = proJob ? null : await unsafeFetchClaudeJobById(sourceJobId);
    const sourceJob = proJob || magicJob;

    if (!sourceJob) {
      return res.status(404).json({ message: "Source job not found" });
    }

    // Verify org ownership
    if (sourceJob.organizationId !== req.user.userData!.organizationId) {
      return res.status(401).json({ message: "You do not own the source job" });
    }

    // Determine original repo for access control
    const checkOrgName = sourceJob.originalOrgName ?? sourceJob.orgName;
    const checkRepoName = sourceJob.originalRepoName ?? sourceJob.repoName;

    // Verify access to original repo (handles access revocation)
    const hasOriginalAccess = await checkUserRepoAccess(req.user, checkOrgName, checkRepoName);
    if (!hasOriginalAccess) {
      return res.status(401).json({ message: "You do not have access to the original repo" });
    }

    // Set provenance fields
    // NOTE: We allow composing from any job status (QUEUED, RUNNING, SUCCESS, ERROR, STOPPED)
    forkedFromId = sourceJob.id;
    forkedFromType = proJob ? "Job" : "ClaudeJob";
    originalOrgName = sourceJob.originalOrgName ?? sourceJob.orgName;
    originalRepoName = sourceJob.originalRepoName ?? sourceJob.repoName;
  }

  let suppliedMetadata: any = {
    startedBy: createHash("sha256").update(userId).digest("hex"),
    method: metadataMethod,
  };

  let metadata;
  try {
    metadata = await getMetaData(suppliedMetadata, orgName, repoName, ref);
  } catch {
    console.log("Job: couldn't create access token");
  }

  //TODO 0XSI
  // After Corn engagement, remove this line
  const isCorn =
    (orgName.toLowerCase() === "usecorn") ||
    (req.user.userData!.organizationId == "7e658035-9e30-4495-9fbe-f6277888afe1");
  const isAllowedScripts = isCorn;

  let otherScript = undefined;
  if (isCorn && repoName === "bitcorn-oft") {
    otherScript = `yarn install`;
  } else if (isCorn && repoName === "airdrop-contracts") {
    otherScript = `echo "y" && pnpm install`;
  }

  // Create the job
  const job = await createJob(
    req.user.userData!.organizationId,
    orgName,
    repoName,
    ref,
    fuzzerType,
    label,
    {
      fuzzerArgs,
      directory,
      duration,
      preprocess: sanitizePreprocess(
        preprocess,
        isAllowedScripts,
        otherScript
      ),
      metadata: metadata ? metadata : suppliedMetadata,
      forkedFromId,
      forkedFromType,
      originalOrgName,
      originalRepoName,
    },
    recipeId
  );

  // await runStarterLoop(); /// @audit Let's use the Cron to prevent double queueing

  return res.json({ message: `Created a Job for your org`, data: job });
}

/// === START JOBS ROUTES === ///
// Unified route that handles all fuzzer types
router.post(
  "/:fuzzerType(medusa|echidna|foundry|halmos|kontrol)",
  onlyLoggedIn,
  requireProOrg,
  orgCheck,
  sanitizeInput,
  extractFuzzerFromUrl,
  createJobHandler
);

router.post(
  "/canclone",
  onlyLoggedIn,
  requireProOrg,
  sanitizeInput,
  async (req: Request, res: Response) => {
    // Get params from Body
    const { orgName, repoName } = req.body;
    // ORG CHECK
    if (!req.user.userData?.organizationId) {
      res.status(400);
      return res.json({
        message: "Your account doesn't belong to an ORG, please talk to staff",
        data: {},
      });
    }
    try {

      const { token } = await getCloneUrlAndToken(orgName, repoName);
      let app;
      if (token) {
        app = initOctokit(token);
      } else {
        app = initOctokit();
      }
      const { data: repo } = await app.rest.repos.get({
        owner: orgName,
        repo: repoName,
      });
      res.status(200);
      return res.json({
        message: "Repository accessible",
        data: {
          name: repo.name,
          private: repo.private,
          hasAccess: true
        }
      });
    } catch (err) {
      console.log(err);
      res.status(404);
      return res.json({ message: `Error checking if we can clone`, data: err });
    }
  }
);



// Get one Job by ID
// Must be in the Org or it won't be found
router.get(
  "/:jobId",
  onlyLoggedIn,
  orgCheck,
  sanitizeInput,
  async (req: Request, res: Response) => {
    const { jobId } = req.params;

    const job = await getOneOrgJob(req.user.userData!.organizationId, jobId);

    if (!job) {
      res.status(404);
      return res.json({ message: "Not Found" });
    }

    return res.json({ message: `Data for job with id: ${jobId}`, data: job });
  }
);

// Get All Jobs for the Org
router.get("/", onlyLoggedIn, orgCheck, async (req: Request, res: Response) => {
  const allJobs = await getAllOrgJobs(req.user.userData!.organizationId);

  return res.json({ message: `Data for jobs in your org`, data: allJobs });
});

// Get All Jobs for the Org that are Running
router.get(
  "/running",
  onlyLoggedIn,
  orgCheck,
  async (req: Request, res: Response) => {
    const allJobs = await getAllRunningOrgJobs(
      req.user.userData!.organizationId
    );

    return res.json({
      message: `Data for  all running jobs in your org`,
      data: allJobs,
    });
  }
);

// Get All Jobs for the Org that are Errored
router.get(
  "/errored",
  onlyLoggedIn,
  orgCheck,
  async (req: Request, res: Response) => {
    const allJobs = await getAllErroredOrgJobs(
      req.user.userData!.organizationId
    );

    return res.json({
      message: `Data for all errored jobs in your org`,
      data: allJobs,
    });
  }
);

// Get All Jobs for the Org that have Ended
router.get(
  "/ended",
  onlyLoggedIn,
  orgCheck,
  async (req: Request, res: Response) => {
    const allJobs = await getAllEndedOrgJobs(req.user.userData!.organizationId);

    return res.json({
      message: `Data for all ended jobs in your org`,
      data: allJobs,
    });
  }
);

router.put(
  "/stop/:jobId",
  onlyLoggedIn,
  orgCheck,
  sanitizeInput,
  async (req: Request, res: Response) => {
    const { jobId } = req.params;

    // We need to confirm that the job is linked to the specific org
    try {
      // This function find a job where the orgId of the user and the jobId match
      // If this throws then the user doesn't have permission to stop the job
      // We may want to extend this to allow any user within an org to stop a job
      await getOneOrgJob(req.user.userData!.organizationId, jobId); /// @audit Improvement: StopJob by Id and Org and throw if not found

      // Update the DB
      const job = await stopJob(jobId);

      return res.json({
        message: `The job has been stopped`,
        data: job,
      });
    } catch {
      res.status(400);
      return res.json({
        message: "Unauthorized",
        data: {},
      });
    }
  }
);

router.get(
  "/brokenProperty/:jobId",
  onlyLoggedIn,
  orgCheck,
  async (req: Request, res: Response) => {
    const { jobId } = req.params;
    const brokenProps = await getBrokenPropertiesForJob(jobId);

    res.status(200);
    return res.json({
      message: `Broken Properties for job with id: ${jobId}`,
      data: brokenProps,
    });
  }
);

router.post(
  "/brokenProperty/:jobId",
  onlyRunner,
  async (req: Request, res: Response) => {
    const { jobId } = req.params;
    const { brokenProperty, traces } = req.body;
    const job = await fetchOneJob(jobId);
    if (!job) {
      res.status(404);
      return res.json({ message: "Job not found" });
    }
    const createBrokenProp = await createBrokenProperty(
      jobId,
      brokenProperty,
      traces
    );

    res.status(201);
    return res.json({
      message: `Broken Property created for job with id: ${jobId}`,
      data: createBrokenProp,
    });
  }
);

router.put("/:jobId", onlyRunner, async (req: Request, res: Response) => {
  const { jobId } = req.params;
  const {
    testsCoverage,
    testsDuration,
    testsFailed,
    testsPassed,
    numberOfTests,
  } = req.body;
  const update = await updateJobRunData(
    jobId,
    testsDuration,
    testsCoverage,
    testsFailed,
    testsPassed,
    numberOfTests
  );
  if (!update) {
    res.status(404);
    return res.json({ message: "Job not found" });
  }

  return res.json({
    message: `Job with id: ${jobId} has been updated`,
    data: update,
  });
});

router.put(
  "/label/:jobId",
  onlyLoggedIn,
  orgCheck,
  sanitizeInput,
  async (req: Request, res: Response) => {
    const { jobId } = req.params;
    const { newLabel } = req.body;

    try {
      // Find the job
      const job = await getOneOrgJob(req.user.userData!.organizationId, jobId);
      if (!job) {
        res.status(404);
        return res.json({
          message: `No job found for id: ${jobId}`,
          data: {},
        });
      }
      
      await updateJobLabel(jobId, newLabel);
      return res.json({
        message: `The job ${jobId} has been updated`,
        data: "job",
      });
    } catch (err) {
      res.status(400);
      return res.json({
        message: "Unauthorized",
        data: {},
      });
    }
  }
);

router.post(
  "/rerun/:jobId",
  onlyLoggedIn,
  requireProOrg,
  orgCheck,
  async (req: Request, res: Response) => {
    try {
      const { jobId } = req.params;
      const orgId = req.user.userData!.organizationId;

      if (!jobId) {
        res.status(400);
        return res.json({
          message: "No job id provided",
          data: {},
        });
      }

      const job = await fetchOneJob(jobId);
      if (!job) {
        res.status(404);
        return res.json({
          message: "Job not found",
          data: {},
        });
      }

      if (job.organizationId !== orgId) {
        res.status(400);
        return res.json({
          message: "Unauthorized",
          data: {},
        });
      }

      let suppliedMetadata: any = {
        startedBy: createHash("sha256")
          .update(req.user.id.toString())
          .digest("hex"),
        method: "website",
      };

      let metadata;
      try {
        metadata = await getMetaData(
          suppliedMetadata,
          job.orgName,
          job.repoName,
          job.ref
        );
      } catch {
        console.log("Job: couldn't create access token");
      }

      const newJob = await createdJobFromPrevJob({
        ...job,
        metadata: metadata,
      });

      return res.json({
        message: "Job rerun successfully",
        data: { job: newJob },
      });
    } catch (error) {
      console.error("Error rerunning job:", error);
      res.status(500);
      return res.json({
        message: "Failed to rerun job",
        data: {},
      });
    }
  }
);

// Runner specific route because we need the logs url correctly formatted and accessible in the runner
router.get(
  "/runner/:jobId",
  onlyRunner,
  async (req: Request, res: Response) => {
    const { jobId } = req.params;
    const job = await fetchOneJob(jobId);
    console.log("job", job);
    return res.json({ message: "Job fetched", data: job });
  }
);
