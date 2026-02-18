import { FUZZER, Job, JobStatus } from "@prisma/client";
import { getSignedUrl } from "../aws/cloudfront";
import prisma from "./client";

export function log(job: Job): Job {
  if (
    process.env.NODE_ENV === "development" &&
    Boolean(process.env.UNSAFE_SKIP_ADMIN_CHECKS) === true
  ) {
    return job;
  }
  if (job.logsUrl) {
    job.logsUrl = getSignedUrl(job.logsUrl);
  }
  if (job.corpusUrl) {
    job.corpusUrl = getSignedUrl(job.corpusUrl);
  }
  if (job.coverageUrl) {
    job.coverageUrl = getSignedUrl(job.coverageUrl);
  }
  return job;
}

function logs(jobs: Job[]): Job[] {
  return jobs.map((job) => log(job));
}

export async function fetchAllJobs() {
  return logs(
    await prisma.job.findMany({
      include: {
        brokenProperties: true,
      },
    })
  );
}

export async function fetchOneJob(jobId: string) {
  return log(
    await prisma.job.findFirstOrThrow({
      where: {
        id: jobId,
      },
      include: {
        brokenProperties: true,
      },
    })
  );
}

export async function fetchLatestJobForRepo(
  organizationId: string,
  orgName: string,
  repoName: string
) {
  return await prisma.job.findFirst({
    where: {
      organizationId,
      orgName,
      repoName,
    },
    orderBy: {
      updatedAt: "desc",
    },
    include: {
      brokenProperties: true,
    },
  });
}

export async function deleteAJob(jobId: string) {
  return await prisma.$transaction(async (prisma) => {
    // First delete related GithubData records
    await prisma.githubData.deleteMany({
      where: {
        jobId: jobId,
      },
    });

    // Delete related broken properties
    await prisma.brokenProperty.deleteMany({
      where: {
        jobId: jobId,
      },
    });

    // Then delete the job
    return await prisma.job.delete({
      where: {
        id: jobId,
      },
    });
  });
}

// Update arb command and queue the job again
export async function updateJobArbitrary(
  jobId: string,
  arbitraryCommand: string
) {
  return await prisma.job.update({
    where: {
      id: jobId,
    },
    data: {
      status: JobStatus.QUEUED,
      arbitraryCommand,
    },
  });
}

// Update job status to STOPPED
// Triggers a graceful termination in runner
export async function stopJob(jobId: string) {
  return await prisma.job.update({
    where: {
      id: jobId,
    },
    data: {
      status: JobStatus.STOPPED,
    },
  });
}

export async function createdJobFromPrevJob(prevJob: Job) {
  return await prisma.job.create({
    data: {
      organizationId: prevJob.organizationId,
      orgName: prevJob.orgName,
      repoName: prevJob.repoName,
      ref: prevJob.ref,
      fuzzer: prevJob.fuzzer,
      label: prevJob.label,
      status: JobStatus.QUEUED,

      // Copy all optional parameters
      fuzzerArgs: prevJob.fuzzerArgs || undefined,
      directory: prevJob.directory,
      duration: prevJob.duration,
      preprocess: prevJob.preprocess,
      arbitraryCommand: prevJob.arbitraryCommand,
      metadata: prevJob.metadata || undefined, // is actually the new metadata

      // Don't copy the recurringJobId as this is a new instance
    },
  });
}

export async function createJob(
  organizationId: string,
  orgName: string,
  repoName: string,
  ref: string,
  fuzzer: FUZZER,
  label: string,
  optionalParams?: {
    fuzzerArgs?: object | string;
    directory?: string;
    duration?: number;
    preprocess?: string;
    arbitraryCommand?: string;
    recurringJobId?: string;
    metadata?: any;
    // Composition fields (polymorphic provenance)
    forkedFromId?: string;
    forkedFromType?: "Job" | "ClaudeJob";
    originalOrgName?: string;
    originalRepoName?: string;
  },
  recipeId: string | null = null
) {
  return await prisma.job.create({
    data: {
      organizationId,
      orgName,
      repoName,
      ref,
      fuzzer,
      label,
      status: JobStatus.QUEUED,

      fuzzerArgs: optionalParams?.fuzzerArgs
        ? optionalParams.fuzzerArgs
        : undefined,

      // Optional Params
      directory: optionalParams?.directory ? optionalParams.directory : ".",
      duration: optionalParams?.duration ? optionalParams.duration : undefined,
      preprocess: optionalParams?.preprocess
        ? optionalParams.preprocess
        : undefined,
      arbitraryCommand: optionalParams?.arbitraryCommand
        ? optionalParams.arbitraryCommand
        : undefined,

      metadata: optionalParams?.metadata ? optionalParams.metadata : undefined,

      // Recurring Job
      recurringJobId: optionalParams?.recurringJobId
        ? optionalParams.recurringJobId
        : undefined,
      recipeId: recipeId,

      // Composition fields (polymorphic provenance)
      forkedFromId: optionalParams?.forkedFromId,
      forkedFromType: optionalParams?.forkedFromType,
      originalOrgName: optionalParams?.originalOrgName,
      originalRepoName: optionalParams?.originalRepoName,
    },
  });
}

export async function getOneOrgJob(organizationId: string, jobId: string) {
  return log(
    await prisma.job.findFirstOrThrow({
      where: {
        organizationId,
        id: jobId,
      },
      include: {
        brokenProperties: true,
        recipe: {
          include: {
            alerts: true,
          },
        },
      },
    })
  );
}

// Return all jobs
// Sorted by most recent by default
// NOTE: No pagination for now
export async function getAllOrgJobs(organizationId: string, latestPrio = true) {
  const jobsWithBrokenProperties = await prisma.job.findMany({
    take: 100,
    where: {
      organizationId,
    },
    orderBy: {
      updatedAt: latestPrio ? "desc" : "asc",
    },
    include: {
      brokenProperties: true,
      recipe: {
        include: {
          alerts: true,
        },
      },
    },
  });
  return logs(jobsWithBrokenProperties);
}

// Return all running
// Sorted by most recent by default
// NOTE: No pagination for now
export async function getAllRunningOrgJobs(
  organizationId: string,
  latestPrio = true
) {
  return logs(
    await prisma.job.findMany({
      where: {
        organizationId,
        OR: [
          {
            status: JobStatus.QUEUED,
          },
          {
            status: JobStatus.RUNNING,
          },
          {
            status: JobStatus.STARTED,
          },
        ],
      },
      orderBy: {
        updatedAt: latestPrio ? "desc" : "asc",
      },
      include: {
        brokenProperties: true,
      },
    })
  );
}

export async function getAllErroredOrgJobs(
  organizationId: string,
  latestPrio = true
) {
  return logs(
    await prisma.job.findMany({
      where: {
        organizationId,
        status: JobStatus.ERROR,
      },
      orderBy: {
        updatedAt: latestPrio ? "desc" : "asc",
      },
      include: {
        brokenProperties: true,
      },
    })
  );
}

export async function getAllEndedOrgJobs(
  organizationId: string,
  latestPrio = true
) {
  return logs(
    await prisma.job.findMany({
      where: {
        organizationId,
        OR: [
          {
            status: JobStatus.STOPPED,
          },
          {
            status: JobStatus.SUCCESS,
          },
        ],
      },
      orderBy: {
        updatedAt: latestPrio ? "desc" : "asc",
      },
      include: {
        brokenProperties: true,
      },
    })
  );
}

export async function updateJobLabel(jobId: string, newLabel: string) {
  try {
    log(
      await prisma.job.update({
        where: {
          id: jobId,
        },
        data: {
          label: newLabel,
        },
      })
    );
  } catch (er) {
    console.log("error:", er);
  }
}

export async function getAllQueuedJob() {
  const jobs = await prisma.job.findMany({
    where: {
      status: "QUEUED",
    },
    orderBy: {
      createdAt: "desc",
    },
  });
  return jobs;
}

export async function getCountOfRunningJobs() {
  const count = await prisma.job.count({
    where: {
      status: "RUNNING",
    },
  });
  return count;
}

// Used in Admin panel
export async function getOrgInfo(orgId: string) {
  const jobs = await prisma.job.findMany({
    where: {
      organizationId: orgId,
    },
    orderBy: {
      createdAt: "desc",
    },
    take: 25,
  });
  const recipes = await prisma.recipe.findMany({
    where: {
      organizationId: orgId,
    },
    include: {
      alerts: true,
    },
  });
  const campaigns = await prisma.campaign.findMany({
    where: {
      organizationId: orgId,
    },
  });
  const recurringJobs = await prisma.recurringJob.findMany({
    where: {
      organizationId: orgId,
    },
    include: {
      alerts: true,
    },
  });
  return {
    jobs,
    recipes,
    campaigns,
    recurringJobs,
  };
}
