import { CLAUDE_JOB_STATUS } from "@prisma/client";
import prisma from "./client";
import { isMagicJobsPaused } from "./systemSettings";


export async function createClaudeJob(
  organizationId: string,

  orgName: string,
  repoName: string,
  ref: string,

  fuzzerName: string,

  claudeOrgName: string,
  claudeRepoName: string,
  claudeRef: string,

  claudePromptCommand: string,

  workflowName: string,

  optionalParams?: {
    directory?: string;
    preprocess?: string;
    // userIDs?: string[]; TODO: User Ids to invite, prob add to extra data
    // Composition fields (polymorphic provenance)
    forkedFromId?: string;
    forkedFromType?: "Job" | "ClaudeJob";
    originalOrgName?: string;
    originalRepoName?: string;
  },

  additionalData?: {
    userHandles?: string[];
    foundryRoot?: string;  // For monorepo support - relative path to foundry.toml directory
  },

) {

  return await prisma.claudeJob.create({
    data: {
      organizationId,
      orgName,
      repoName,
      ref,
      fuzzerName,
      claudeOrgName,
      claudeRepoName,
      claudeRef,
      claudePromptCommand,

      workflowName,

      directory: optionalParams?.directory,
      preprocess: optionalParams?.preprocess,
      forkedFromId: optionalParams?.forkedFromId,
      forkedFromType: optionalParams?.forkedFromType,
      originalOrgName: optionalParams?.originalOrgName,
      originalRepoName: optionalParams?.originalRepoName,
      additionalData: additionalData || {}, // Avoids null
    },
    omit: {
      claudeOrgName: true,
      claudeRepoName: true,
      claudeRef: true,
      claudePromptCommand: true,
    },
  });
}

export async function fetchAllClaudeJobs() {
  return await prisma.claudeJob.findMany({
    orderBy: {
      updatedAt: "desc",
    },
    take: 100,
  });
}

/// @audit NOTE: Privacy leak, we return all fields since this is used by Claude Service
export async function fetchPendingJobs() {
  // Check if magic jobs are paused by super admin
  const paused = await isMagicJobsPaused();
  if (paused) {
    return []; // Return empty array when paused - worker will just wait
  }

  return await prisma.claudeJob.findMany({
    where: {
      claudeJobStatus: CLAUDE_JOB_STATUS.QUEUED,
    },
    // No order by since we want to handle FIFO
  });
}

// Count pending jobs in queue (public-safe, no details exposed)
export async function countPendingJobs() {
  return await prisma.claudeJob.count({
    where: {
      claudeJobStatus: CLAUDE_JOB_STATUS.QUEUED,
    },
  });
}

export async function fetchOrgJobs(organizationId: string) {
  return await prisma.claudeJob.findMany({
    where: {
      organizationId,
    },
    orderBy: {
      createdAt: "desc",
    },
    /// @audit PRIVACY. Hide prompt details
    omit: {
      claudeOrgName: true,
      claudeRepoName: true,
      claudeRef: true,
      claudePromptCommand: true,
    },
    take: 100,
  });
}

export async function unsafeFetchClaudeJobById(jobId: string) {
  return await prisma.claudeJob.findUnique({
    where: { id: jobId },
  });
}
export async function fetchClaudeJobById(jobId: string, organizationId: string) {
  return await prisma.claudeJob.findUnique({
    where: { id: jobId, organizationId },
  });
}

export async function updateClaudeJobStatus(jobId: string, status: CLAUDE_JOB_STATUS) {
  return await prisma.claudeJob.update({
    where: { id: jobId },
    data: { claudeJobStatus: status },
  });
}

export async function updateClaudeJobAdditionalData(jobId: string, additionalData: any) {
  return await prisma.claudeJob.update({
    where: { id: jobId },
    data: { additionalData: additionalData },
  });
}

export async function updateClaudeJobResult(jobId: string, resultData: any) {
  return await prisma.claudeJob.update({
    where: { id: jobId },
    data: { claudeJobStatus: CLAUDE_JOB_STATUS.DONE, resultData: resultData },
  });
}

export async function updateClaudeJobResultWithStatus(jobId: string, resultData: any, status: CLAUDE_JOB_STATUS) {
  return await prisma.claudeJob.update({
    where: { id: jobId },
    data: { claudeJobStatus: status, resultData: resultData },
  });
}

// Update only resultData without changing status
export async function updateClaudeJobResultData(jobId: string, resultData: any) {
  return await prisma.claudeJob.update({
    where: { id: jobId },
    data: { resultData: resultData },
  });
}


export async function deleteClaudeJob(jobId: string) {
  return await prisma.claudeJob.delete({
    where: { id: jobId },
  });
}

export async function deleteOrgJob(jobId: string, organizationId: string) {
  return await prisma.claudeJob.delete({
    where: { id: jobId, organizationId },
  });
}

export async function requestStopClaudeJob(jobId: string, organizationId: string) {
  return await prisma.claudeJob.update({
    where: { id: jobId, organizationId },
    data: { stopRequested: true },
  });
}

export async function skipClaudeJob(jobId: string, organizationId: string, skipStepId: string) {
  // Fetch the job to verify ownership and existence
  const job = await prisma.claudeJob.findUnique({
    where: { id: jobId },
  });
  
  if (!job) {
    throw new Error("Job not found");
  }

  if (job.organizationId !== organizationId) {
    throw new Error("Not authorized to modify this job");
  }

  const existingData = (job.additionalData as any) || {};
  
  return await prisma.claudeJob.update({
    where: { id: jobId },
    data: {
      additionalData: {
        ...existingData,
        skipStepId,
      },
    },
  });
}

export async function checkStopRequested(jobId: string) {
  const job = await prisma.claudeJob.findUnique({
    where: { id: jobId },
    select: { stopRequested: true },
  });
  return job?.stopRequested ?? false;
}

/**
 * Resume an existing ClaudeJob from a specific step.
 * Updates the job status to QUEUED and stores resumeFromStepId in additionalData.
 * The worker will pick it up and start from the specified step.
 */
export async function resumeClaudeJob(
  jobId: string,
  resumeFromStepId: string,
  organizationId: string
) {
  // Fetch the job to verify ownership and existence
  const job = await prisma.claudeJob.findUnique({
    where: { id: jobId },
  });

  if (!job) {
    throw new Error("Job not found");
  }

  if (job.organizationId !== organizationId) {
    throw new Error("Not authorized to resume this job");
  }

  // Build updated additionalData with resume information
  const existingAdditionalData = (job.additionalData as any) || {};
  const updatedAdditionalData = {
    ...existingAdditionalData,
    resumeFromStepId: resumeFromStepId,
    resumedAt: new Date().toISOString(),
  };

  // Preserve existing resultData but remove the target step and all subsequent steps
  const existingResultData = (job.resultData as any) || {};
  const existingSteps = (existingResultData.steps as any[]) || [];
  
  // Find the index of the step we're resuming from (steps use 'internal_id' field)
  const resumeStepIndex = existingSteps.findIndex((step: any) => step.internal_id === resumeFromStepId);
  
  // Keep only steps before the resume step (remove the resume step and everything after)
  const filteredSteps = resumeStepIndex >= 0 
    ? existingSteps.slice(0, resumeStepIndex)
    : existingSteps;
  
  const updatedResultData = {
    ...existingResultData,
    steps: filteredSteps,
    resumeHistory: [
      ...((existingResultData.resumeHistory as any[]) || []),
      {
        stepId: resumeFromStepId,
        timestamp: new Date().toISOString(),
        removedSteps: resumeStepIndex >= 0 ? existingSteps.length - resumeStepIndex : 0,
      },
    ],
  };

  // Update the job: reset status to QUEUED, clear stop flag, update resume info
  return await prisma.claudeJob.update({
    where: { id: jobId },
    data: {
      claudeJobStatus: CLAUDE_JOB_STATUS.QUEUED,
      stopRequested: false,
      additionalData: updatedAdditionalData,
      resultData: updatedResultData,
    },
    omit: {
      claudeOrgName: true,
      claudeRepoName: true,
      claudeRef: true,
      claudePromptCommand: true,
    },
  });
}