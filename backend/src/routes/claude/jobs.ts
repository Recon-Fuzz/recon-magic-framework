import { Request, Response } from "express";

import express from "express";
import {  onlyClaude, onlyLoggedIn, requireProOrg } from "../../middleware/auth";
import { checkStopRequested, countPendingJobs, createClaudeJob, resumeClaudeJob, deleteOrgJob, requestStopClaudeJob, unsafeFetchClaudeJobById, fetchOrgJobs, fetchPendingJobs, updateClaudeJobAdditionalData, updateClaudeJobResult, updateClaudeJobResultData, updateClaudeJobResultWithStatus, updateClaudeJobStatus, skipClaudeJob } from "../../db/claudeJobs";
import { fetchOneJob } from "../../db/jobs";
import { CLAUDE_JOB_STATUS, ClaudeJob } from "@prisma/client";
import { getCloneUrlAndToken, checkUserRepoAccess } from "../../github/installations";
import { getCommitDiff } from "../../github/claude-specific";
import { getOrgMagicCredits, decrementOrgMagicCredit } from "../../db/magicCredits";

const router = express.Router();
export default router;

// UUID validation helper
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Public: Get queue count (no auth required, just returns a number)
router.get("/queue/count", async (req: Request, res: Response) => {
  const count = await countPendingJobs();
  return res.json({
    message: "Queue count",
    count,
  });
});

// Allow viewing jobs for Pro users OR users who have/had magic credits
router.get("/", onlyLoggedIn, async (req: Request, res: Response) => {
  const jobs = await fetchOrgJobs(req.user.userData!.organizationId);
  return res.json({
    message: "Here are the jobs",
    data: jobs,
  });
});

router.post("/", onlyLoggedIn, requireProOrg, async (req: Request, res: Response) => {
  const {
    orgName,
    repoName,
    ref,

    workflowType,

    // fuzzerName,

    // claudeOrgName,
    // claudeRepoName,
    // claudeRef,

    // claudePromptCommand,
    userHandles,

    optionalParams,
    sourceJobId
   } = req.body;

   if(!req.user.userData) {
    return res.status(401).json({
      message: "You must be logged in to create a job",
    });
   }

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
     const proJob = await fetchOneJob(sourceJobId);
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
     // NOTE: We allow composing from any job status
     forkedFromId = sourceJob.id;
     forkedFromType = proJob ? "Job" : "ClaudeJob";
     originalOrgName = sourceJob.originalOrgName ?? sourceJob.orgName;
     originalRepoName = sourceJob.originalRepoName ?? sourceJob.repoName;
   }

   const fuzzerName = "echidna";
   const claudeOrgName = "Recon-Fuzz";
   const claudeRepoName = "ai-agent-primers";
   const claudeRef = "main";

   let claudePromptCommand = "";
   let workflowName = "Recon Magic";

   if(workflowType === "unit-0") {
    workflowName = `Unit Test - ${optionalParams.contractName}`;
    claudePromptCommand = `
You are provided a repo at ./repo and custom agent definitions at ./.claude. 
Please check the README in ./.claude then  Use ./repo as your working directory. 
Run every agentic worfklow from unit-phase-0 to unit-phase-5 using the Task tool.
Perform the agentic workflow on the contract ${optionalParams.contractName}.`;
   }

   if(workflowType === "phase-2") {
    workflowName = "Scaffold Coverage";
    claudePromptCommand = `
You are provided a repo at ./repo and custom agent definitions at ./.claude. 
Please check the README in ./.claude then
Use ./repo as your working directory. 
Run every agentic worfklow from coverage-phase-0 to coverage-phase-5 using the Task tool;
`
  }

  if(workflowType === "properties-0") {
    workflowName = "Identify Invariants";
    claudePromptCommand = `
You are provided a repo at ./repo and custom agent definitions at ./.claude. 
Please check the README in ./.claude then
Use ./repo as your working directory. 
Run every agentic worfklow from properties-phase-0 to properties-phase-2 using the Task tool;
`
  }
  if(workflowType === "audit-naive-0") {
    workflowName = "AI Powered Audit";
    claudePromptCommand = `
You are provided a repo at ./repo and custom agent definitions at ./.claude.
Please check the README in ./.claude then
Use ./repo as your working directory.
Run every agentic worfklow from audit-naive-phase-0 to audit-naive-phase-6 using the Task tool;
`
  }

  // coverage-v2 uses framework workflow mode
  let jobType = "directPrompt";

  if(workflowType === "scout-v2") {
    workflowName = "workflow-fuzzing-scouting";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  if(workflowType === "setup-v2") {
    workflowName = "workflow-fuzzing-setup";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  if(workflowType === "coverage-v2") {
    workflowName = "workflow-fuzzing-coverage";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  // Compositional workflows
  if(workflowType === "compose-setup-coverage") {
    workflowName = "compose-setup-coverage";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  if(workflowType === "compose-scout-setup-coverage") {
    workflowName = "compose-scout-setup-coverage";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  if(workflowType === "compose-setup-properties-coverage") {
    workflowName = "compose-setup-properties-coverage";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  if(workflowType === "compose-scout-setup-properties-coverage") {
    workflowName = "compose-scout-setup-properties-coverage";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  if(workflowType === "workflow-properties-full") {
    workflowName = "workflow-properties-full";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  if(workflowType === "workflow-properties-full-opus") {
    workflowName = "workflow-properties-full-opus";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  // Coverage + Properties combined workflow (for existing setups)
  if(workflowType === "compose-coverage-properties") {
    workflowName = "compose-coverage-properties";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  // Fuzz-only workflow for testing - only dispatches a fuzzing job
  if(workflowType === "fuzz-only") {
    workflowName = "workflow-fuzz-only";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }



  // NOTE: Optional params are directory and preprocess, not currently used, spreading causes reverts
  // const enrichedOptionalParams = {
  //   ...(optionalParams || {})
  //  };

  const additionalData = {
    userHandles: userHandles,
    contractName: optionalParams?.contractName,
    foundryRoot: optionalParams?.foundryRoot,  // For monorepo support
    jobType,
  };



  // NOTE: Enforce by `requireProOrg`
  const job = await createClaudeJob(
    req.user.userData!.organizationId,
    orgName,
    repoName,
    ref,
    fuzzerName,
    claudeOrgName,
    claudeRepoName,
    claudeRef,
    claudePromptCommand,
    workflowName,
    {
      forkedFromId,
      forkedFromType,
      originalOrgName,
      originalRepoName,
    },
    additionalData
  );
  return res.json({
    message: "Job created",
    data: job,
  });
});

// Create a magic job using an org's magic credit (for free users)
router.post("/with-credit", onlyLoggedIn, async (req: Request, res: Response) => {
  const {
    orgName,
    repoName,
    ref,
    workflowType,
    userHandles,
    optionalParams,
    sourceJobId
  } = req.body;

  if (!req.user.userData) {
    return res.status(401).json({
      message: "You must be logged in to create a job",
    });
  }

  const orgId = req.user.userData.organizationId;

  // Check if org has credits
  const credits = await getOrgMagicCredits(orgId);
  if (credits < 1) {
    return res.status(403).json({
      error: "NO_CREDITS",
      message: "No magic credits available. Redeem an invite code first.",
    });
  }

  const hasAccess = await checkUserRepoAccess(req.user, orgName, repoName);
  if (!hasAccess) {
    return res.status(401).json({
      message: "You do not have access to this repo",
    });
  }

  // Composition fields (set if sourceJobId is provided)
  let forkedFromId: string | undefined;
  let forkedFromType: "Job" | "ClaudeJob" | undefined;
  let originalOrgName: string | undefined;
  let originalRepoName: string | undefined;

  if (sourceJobId) {
    if (!UUID_REGEX.test(sourceJobId)) {
      return res.status(400).json({ message: "Invalid sourceJobId format" });
    }

    const proJob = await fetchOneJob(sourceJobId);
    const magicJob = proJob ? null : await unsafeFetchClaudeJobById(sourceJobId);
    const sourceJob = proJob || magicJob;

    if (!sourceJob) {
      return res.status(404).json({ message: "Source job not found" });
    }

    if (sourceJob.organizationId !== orgId) {
      return res.status(401).json({ message: "You do not own the source job" });
    }

    const checkOrgName = sourceJob.originalOrgName ?? sourceJob.orgName;
    const checkRepoName = sourceJob.originalRepoName ?? sourceJob.repoName;

    const hasOriginalAccess = await checkUserRepoAccess(req.user, checkOrgName, checkRepoName);
    if (!hasOriginalAccess) {
      return res.status(401).json({ message: "You do not have access to the original repo" });
    }

    forkedFromId = sourceJob.id;
    forkedFromType = proJob ? "Job" : "ClaudeJob";
    originalOrgName = sourceJob.originalOrgName ?? sourceJob.orgName;
    originalRepoName = sourceJob.originalRepoName ?? sourceJob.repoName;
  }

  const fuzzerName = "echidna";
  const claudeOrgName = "Recon-Fuzz";
  const claudeRepoName = "ai-agent-primers";
  const claudeRef = "main";

  let claudePromptCommand = "";
  let workflowName = "Recon Magic";
  let jobType = "directPrompt";

  // Same workflow type handling as the regular POST route
  if (workflowType === "unit-0") {
    workflowName = `Unit Test - ${optionalParams.contractName}`;
    claudePromptCommand = `
You are provided a repo at ./repo and custom agent definitions at ./.claude.
Please check the README in ./.claude then  Use ./repo as your working directory.
Run every agentic worfklow from unit-phase-0 to unit-phase-5 using the Task tool.
Perform the agentic workflow on the contract ${optionalParams.contractName}.`;
  }

  if (workflowType === "phase-2") {
    workflowName = "Scaffold Coverage";
    claudePromptCommand = `
You are provided a repo at ./repo and custom agent definitions at ./.claude.
Please check the README in ./.claude then
Use ./repo as your working directory.
Run every agentic worfklow from coverage-phase-0 to coverage-phase-5 using the Task tool;
`;
  }

  if (workflowType === "properties-0") {
    workflowName = "Identify Invariants";
    claudePromptCommand = `
You are provided a repo at ./repo and custom agent definitions at ./.claude.
Please check the README in ./.claude then
Use ./repo as your working directory.
Run every agentic worfklow from properties-phase-0 to properties-phase-2 using the Task tool;
`;
  }

  if (workflowType === "audit-naive-0") {
    workflowName = "AI Powered Audit";
    claudePromptCommand = `
You are provided a repo at ./repo and custom agent definitions at ./.claude.
Please check the README in ./.claude then
Use ./repo as your working directory.
Run every agentic worfklow from audit-naive-phase-0 to audit-naive-phase-6 using the Task tool;
`;
  }

  if (workflowType === "scout-v2") {
    workflowName = "workflow-fuzzing-scouting";
    jobType = "workflowName";
    claudePromptCommand = "";
  }

  if (workflowType === "setup-v2") {
    workflowName = "workflow-fuzzing-setup";
    jobType = "workflowName";
    claudePromptCommand = "";
  }

  if (workflowType === "coverage-v2") {
    workflowName = "workflow-fuzzing-coverage";
    jobType = "workflowName";
    claudePromptCommand = "";
  }

  if (workflowType === "compose-setup-coverage") {
    workflowName = "compose-setup-coverage";
    jobType = "workflowName";
    claudePromptCommand = "";
  }

  if (workflowType === "compose-scout-setup-coverage") {
    workflowName = "compose-scout-setup-coverage";
    jobType = "workflowName";
    claudePromptCommand = "";
  }

  if (workflowType === "compose-setup-properties-coverage") {
    workflowName = "compose-setup-properties-coverage";
    jobType = "workflowName";
    claudePromptCommand = "";
  }

  if (workflowType === "compose-scout-setup-properties-coverage") {
    workflowName = "compose-scout-setup-properties-coverage";
    jobType = "workflowName";
    claudePromptCommand = "";
  }

  if (workflowType === "workflow-properties-full") {
    workflowName = "workflow-properties-full";
    jobType = "workflowName";
    claudePromptCommand = "";
  }

  if (workflowType === "workflow-properties-full-opus") {
    workflowName = "workflow-properties-full-opus";
    jobType = "workflowName";
    claudePromptCommand = "";
  }

  // Coverage + Properties combined workflow (for existing setups)
  if (workflowType === "compose-coverage-properties") {
    workflowName = "compose-coverage-properties";
    jobType = "workflowName";
    claudePromptCommand = "";
  }

  if (workflowType === "fuzz-only") {
    workflowName = "workflow-fuzz-only";
    jobType = "workflowName";
    claudePromptCommand = "";
  }

  const additionalData = {
    userHandles: userHandles,
    contractName: optionalParams?.contractName,
    foundryRoot: optionalParams?.foundryRoot,
    jobType,
  };

  // Create the job
  const job = await createClaudeJob(
    orgId,
    orgName,
    repoName,
    ref,
    fuzzerName,
    claudeOrgName,
    claudeRepoName,
    claudeRef,
    claudePromptCommand,
    workflowName,
    {
      forkedFromId,
      forkedFromType,
      originalOrgName,
      originalRepoName,
    },
    additionalData
  );

  // Consume the credit after successful job creation
  await decrementOrgMagicCredit(orgId);

  return res.json({
    message: "Job created using magic credit",
    data: job,
    creditsRemaining: credits - 1,
  });
});

router.get("/diff/:jobId", onlyLoggedIn, async (req: Request, res: Response) => {
  const { jobId } = req.params;
  const diff = await getCommitDiff(jobId, req.user.userData!.organizationId);
  return res.json({
    message: "Diff",
    data: diff,
  });
});


router.delete("/:jobId", onlyLoggedIn, requireProOrg, async (req: Request, res: Response) => {
  const { jobId } = req.params;
  try {
    const jobs = await deleteOrgJob(jobId, req.user.userData!.organizationId);
    return res.json({
      message: "Job deleted",
        data: jobs,
    });
  } catch (e) {
    console.error("Error deleting job", e);
    return res.status(500).json({
      message: "Error deleting job"
    });
  }
});

// User endpoint: Request graceful stop for a job
router.put("/stop/:jobId", onlyLoggedIn, async (req: Request, res: Response) => {
  const { jobId } = req.params;
  try {
    const job = await requestStopClaudeJob(jobId, req.user.userData!.organizationId);
    return res.json({
      message: "Stop requested for job",
      data: job,
    });
  } catch (e) {
    console.error("Error requesting stop for job", e);
    return res.status(500).json({
      message: "Error requesting stop for job"
    });
  }
});

// User endpoint: Set a step to skip during job execution
router.post("/skip/:jobId", onlyLoggedIn, requireProOrg, async (req: Request, res: Response) => {
  const { jobId } = req.params;
  const { skipStepId } = req.body;

  if (!skipStepId || typeof skipStepId !== "string") {
    return res.status(400).json({
      message: "skipStepId is required and must be a string (e.g., 'audit:2')"
    });
  }

  if (!UUID_REGEX.test(jobId)) {
    return res.status(400).json({
      message: "Invalid job ID format"
    });
  }

  try {
    const job = await skipClaudeJob(jobId, req.user.userData!.organizationId, skipStepId);
    return res.json({
      message: "Skip step set for job",
      data: job,
    });
  } catch (e: any) {
    console.error("Error setting skip step", e);
    return res.status(400).json({
      message: e.message || "Error setting skip step"
    });
  }
});

// User endpoint: Resume a failed/stopped job from a specific step
router.post("/resume/:jobId", onlyLoggedIn, requireProOrg, async (req: Request, res: Response) => {
  const { jobId } = req.params;
  const { resumeFromStepId } = req.body;

  if (!resumeFromStepId || typeof resumeFromStepId !== "string") {
    return res.status(400).json({
      message: "resumeFromStepId is required and must be a string (e.g., 'audit:2')"
    });
  }

  if (!UUID_REGEX.test(jobId)) {
    return res.status(400).json({
      message: "Invalid job ID format"
    });
  }

  try {
    const job = await resumeClaudeJob(
      jobId,
      resumeFromStepId,
      req.user.userData!.organizationId
    );
    return res.json({
      message: "Job queued for resumption from step " + resumeFromStepId,
      data: job,
    });
  } catch (e: any) {
    console.error("Error resuming job", e);
    return res.status(400).json({
      message: e.message || "Error resuming job"
    });
  }
});

/** CLAUDE SIDE | TODO: Add Prefix */
// GET: Returns list of jobs Claude needs to work on
router.get("/worker/", onlyClaude, async (req: Request, res: Response) => {
  const jobs = await fetchPendingJobs();
  return res.json({
    message: "Here are the jobs",
    data: jobs,
  });
});

// Start processing the job
router.get("/worker/:jobId", onlyClaude, async (req: Request, res: Response) => {
  const { jobId } = req.params;

  // Update the job to running and fetch it // Note this can throw
  let job: ClaudeJob | null = null;
  try {
    job = await updateClaudeJobStatus(jobId, CLAUDE_JOB_STATUS.WIP);
  } catch (e) {
    console.error("Error updating job status", e);
    return res.status(404).json({
      message: "Job not found",
    });
  }

  try {
    // Retrieve GH token for repo
    const repoAccessData = await getCloneUrlAndToken(
      job.orgName,
      job.repoName,
    );
    
    // Retrieve GH token for Claude Repo
    const claudeAccessData = await getCloneUrlAndToken(
      job.claudeOrgName,
      job.claudeRepoName,
    )

    if(!repoAccessData.url || !claudeAccessData.url) {
      throw new Error("No access data");
    }

    return res.json({
      message: "Here is the job",
      data: {
        job,
        repoAccessData,
        claudeAccessData,
      },
    });

  } catch (e) {
    await updateClaudeJobStatus(jobId, CLAUDE_JOB_STATUS.ERROR);
    console.error("Error starting job", e);
    return res.status(500).json({
      message: "Error starting job",
      error: e,
    });
  }

  // Note: Will never be hit
});

// PUT: Update a job status and sets result
router.put("/worker/status", onlyClaude, async (req: Request, res: Response) => {
  const { jobId, status } = req.body;

  const job = await updateClaudeJobStatus(jobId, status);
  return res.json({
    message: "Job updated",
    data: job,
  });
});

router.put("/worker/data", onlyClaude, async (req: Request, res: Response) => {
  const { jobId, resultData, skipStepId } = req.body;

  const foundJob = await unsafeFetchClaudeJobById(jobId);

  if(!foundJob) {
    return res.status(404).json({
      message: "Job not found",
    });
  }

    // If skipStepId is provided, update additionalData and return early
  if (skipStepId && typeof skipStepId === "string") {
    const existingAdditionalData = (foundJob.additionalData as any) || {};
    const job = await updateClaudeJobAdditionalData(jobId, {
      ...existingAdditionalData,
      skipStepId,
    });

    return res.json({
      message: "Job updated",
      data: job,
    });
  }

  const existingData = foundJob.resultData as any || {};

  // Special handling for steps array - append instead of overwrite
  let updatedResultData: any;
  if (resultData.steps && Array.isArray(resultData.steps)) {
    const existingSteps = existingData.steps || [];
    updatedResultData = {
      ...existingData,
      ...resultData,
      steps: [...existingSteps, ...resultData.steps]  // Append new steps
    };
  } else {
    updatedResultData = {
      ...existingData,
      ...resultData,
    };
  }

  const job = await updateClaudeJobResultData(jobId, updatedResultData);
  return res.json({
    message: "Job updated",
    data: job,
  });
});

router.put("/worker/end", onlyClaude, async (req: Request, res: Response) => {
  const { jobId, resultData, status } = req.body;

  // Get current job to merge resultData
  const foundJob = await unsafeFetchClaudeJobById(jobId);
  if (!foundJob) {
    return res.status(404).json({ message: "Job not found" });
  }

  const updatedResultData = {
    ...foundJob.resultData as any,
    ...resultData,
  };

  // Determine final status - default to DONE if not provided
  // Valid statuses: DONE, ERROR, STOPPED
  let finalStatus: CLAUDE_JOB_STATUS;
  if (status === "ERROR") {
    finalStatus = CLAUDE_JOB_STATUS.ERROR;
  } else if (status === "STOPPED") {
    finalStatus = CLAUDE_JOB_STATUS.STOPPED;
  } else {
    finalStatus = CLAUDE_JOB_STATUS.DONE;
  }

  // Set job status and update resultData
  const job = await updateClaudeJobResultWithStatus(jobId, updatedResultData, finalStatus);

  // Note: User invites are handled early by the worker (before workflow runs)

  const statusMsg = finalStatus === CLAUDE_JOB_STATUS.ERROR ? "failed" :
                    finalStatus === CLAUDE_JOB_STATUS.STOPPED ? "stopped" : "completed";
  return res.json({
    message: `Job ${statusMsg}`,
    data: job,
  });
});

// Worker endpoint: Check if stop was requested for a job
router.get("/worker/:jobId/stop", onlyClaude, async (req: Request, res: Response) => {
  const { jobId } = req.params;
  try {
    const stopRequested = await checkStopRequested(jobId);
    return res.json({
      message: "Stop status checked",
      stopRequested,
    });
  } catch (e) {
    console.error("Error checking stop status", e);
    return res.status(500).json({
      message: "Error checking stop status",
      stopRequested: false,
    });
  }
});

// Worker endpoint: Dispatch a fuzzing job from a running ClaudeJob
// This allows workflows to spawn fuzzing jobs when they complete setup
router.post("/worker/:jobId/dispatch-fuzzing", onlyClaude, async (req: Request, res: Response) => {
  const { jobId } = req.params;
  const {
    fuzzerType = "echidna",
    duration,  // No default - uses FUZZ_TIMEOUT env var like FE jobs
    directory = ".",
    fuzzerArgs,
    label,
  } = req.body;

  // Default fuzzerArgs for magic-dispatched Echidna jobs
  const defaultEchidnaArgs = {
    testLimit: "10000000",  // 10 million tests
  };

  // Default duration: 4 hours (14400 seconds)
  const defaultDuration = 14400;

  try {
    // Fetch the parent ClaudeJob to get org context and repo info
    const claudeJob = await unsafeFetchClaudeJobById(jobId);
    if (!claudeJob) {
      return res.status(404).json({ message: "ClaudeJob not found" });
    }

    // Get repo info from resultData (set by worker when it creates the GitHub repo)
    const resultData = claudeJob.resultData as any;
    if (!resultData?.repoUrl || !resultData?.orgName || !resultData?.repoName) {
      return res.status(400).json({
        message: "ClaudeJob has no repo info in resultData. Ensure the workflow has created a GitHub repo first.",
        hint: "resultData should contain: repoUrl, orgName, repoName"
      });
    }

    // Validate fuzzer type
    const validFuzzers = ["echidna", "medusa", "foundry", "halmos", "kontrol"];
    const normalizedFuzzer = fuzzerType.toLowerCase();
    if (!validFuzzers.includes(normalizedFuzzer)) {
      return res.status(400).json({
        message: `Invalid fuzzer type: ${fuzzerType}. Must be one of: ${validFuzzers.join(", ")}`
      });
    }

    // Import createJob from jobs db
    const { createJob } = await import("../../db/jobs");

    // Merge provided fuzzerArgs with defaults (provided args take precedence)
    const mergedFuzzerArgs = {
      ...defaultEchidnaArgs,
      ...(fuzzerArgs || {}),
    };

    // Create the fuzzing job, inheriting org from parent ClaudeJob
    const fuzzingJob = await createJob(
      claudeJob.organizationId,           // Inherited from parent
      resultData.orgName,                 // GitHub org (e.g., "Recon-Fuzz")
      resultData.repoName,                // Repo name created by magic
      "main",                             // Magic always pushes to main
      normalizedFuzzer.toUpperCase() as any,  // ECHIDNA, MEDUSA, etc.
      label || `Magic: ${claudeJob.workflowName}`,
      {
        directory,
        duration: duration ?? defaultDuration,  // Default: 4 hours
        fuzzerArgs: mergedFuzzerArgs,
        // Polymorphic provenance - link to parent ClaudeJob
        forkedFromId: jobId,
        forkedFromType: "ClaudeJob",
        metadata: {
          workflowName: claudeJob.workflowName,
          method: "magic-framework"
        }
      }
    );

    // Track the created job in ClaudeJob's resultData
    const existingFuzzingJobs = resultData.dispatchedFuzzingJobs || [];
    await updateClaudeJobResultData(jobId, {
      ...resultData,
      dispatchedFuzzingJobs: [...existingFuzzingJobs, {
        jobId: fuzzingJob.id,
        fuzzerType: normalizedFuzzer,
        createdAt: new Date().toISOString()
      }]
    });

    return res.json({
      message: "Fuzzing job dispatched",
      data: {
        jobId: fuzzingJob.id,
        status: fuzzingJob.status,
        fuzzer: fuzzingJob.fuzzer,
        orgName: fuzzingJob.orgName,
        repoName: fuzzingJob.repoName,
        parentClaudeJobId: jobId
      }
    });

  } catch (e) {
    console.error("Error dispatching fuzzing job", e);
    return res.status(500).json({
      message: "Error dispatching fuzzing job",
      error: String(e)
    });
  }
});

