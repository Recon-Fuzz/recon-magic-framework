import { JobStatus } from "@prisma/client";
import prisma from "../db/client";
import { createJob } from "../db/jobs";
import { isJobValid, makeJobFromRecipe } from "../recipes";
import { RunnableJob } from "../types";
import { getMetaData } from "../utils/metadata";

async function disableRecurringJob(reccuringJobId: string) {
  return await prisma.recurringJob.update({
    where: {
      id: reccuringJobId,
    },
    data: {
      enabled: false,
    },
  });
}
async function updateLastRun(reccuringJobId: string) {
  return await prisma.recurringJob.update({
    where: {
      id: reccuringJobId,
    },
    data: {
      lastRun: new Date(),
    },
  });
}

export async function createJobFromRunnableJob(
  jobInput: RunnableJob,
  recurringJobId: string
) {
  // TODO: Here we can check sanitization and if recipe can't be used we auto toggle it off
  const {
    orgName,
    repoName,
    ref,
    fuzzer,
    organizationId,
    fuzzerArgs,
    directory,
    duration,
    preprocess,
    arbitraryCommand,
  } = jobInput;

  let suppliedMetadata: any = {
    recurringJobId: recurringJobId,
    method: "recurring"
  }

  let metadata;
  try {
    metadata = await getMetaData(suppliedMetadata, orgName, repoName, ref)
  } catch {
    console.log("Job: couldn't create access token");
  }

  const createdJob = await createJob(
    organizationId,
    orgName,
    repoName,
    ref,
    fuzzer,
    jobInput.label ? jobInput.label : "",
    {
      fuzzerArgs: fuzzerArgs,
      directory: directory,
      duration: duration,
      preprocess: preprocess,
      arbitraryCommand: arbitraryCommand,
      recurringJobId,
      metadata: metadata ? metadata : suppliedMetadata // there will always be metadata in this case
    }
  );

  console.log("Created a new job with id", createdJob.id);
}

export default async function runCron() {
  // Get all active recurring jobs
  // Run them
  const recurringJobs = await prisma.recurringJob.findMany({
    where: {
      enabled: true,
    },
    include: {
      recipe: true,
      jobs: true,
    },
  });

  console.log("Recurring Jobs Found Count", recurringJobs.length);

  // For each, check if a job is already running

  await Promise.all(
    recurringJobs.map(async (recJob) => {
      // Early return if not enough time has passed
      if (
        new Date().getTime() - new Date(recJob.lastRun).getTime() <
        recJob.frequencyInSeconds * 1000
      ) {
        // Early return
        console.log("Job not ready yet: ", recJob.id);
        console.log("recJob.lastRun", recJob.lastRun);
        console.log("recJob.frequencyInSeconds", recJob.frequencyInSeconds);
        return;
      }

      // If we already have a job queued, skip
      if (
        recJob.jobs.filter((job) => job.status === JobStatus.QUEUED).length > 0 ||
        recJob.jobs.filter((job) => job.status === JobStatus.RUNNING).length > 0 ||
        recJob.jobs.filter((job) => job.status === JobStatus.STARTED).length > 0
      ) {
        console.log("Job already queued, skipping: ", recJob.id);
        return;
      }

      let asJobInput = {};
      try {
        asJobInput = makeJobFromRecipe({}, recJob.recipe);
      } catch (e) {
        // Nothing, the check below will fail
        console.log("Revert when making job from recipe: ", recJob.id);
        await disableRecurringJob(recJob.id);
        return false;
      }

      // Not runnable ends here
      if (!isJobValid(asJobInput)) {
        console.log("Invalid Recipe for Recurring Job, disabling: ", recJob.id);
        await disableRecurringJob(recJob.id);
        return false;
      }

      // TODO: We could add a even log for each run
      // TimeX: Created
      // TimeY: Ran, etc..
      // Create Job From Recipe

      // Let's Queue the job
      // @ts-ignore We just sanitized it above
      await createJobFromRunnableJob(asJobInput, recJob.id);

      // Let's reset our clock
      await updateLastRun(recJob.id);
    })
  );
}
