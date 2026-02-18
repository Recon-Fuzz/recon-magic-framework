import buildAndReturnABI from "../lib/buildIntoAbi";

import { ABIJOB_STATUS } from "@prisma/client";
import { getLatestCommitForRepo } from "../github/repos";
import { getCloneUrlAndToken } from "../github/installations";
import { AbiJobInput } from "../types";
import { createNewAbiData } from "./abis";
import prisma from "./client";

export async function fetchAllAbiJobs() {
  return await prisma.abiJob.findMany({});
}
export async function fetchAllAbiJobsFromOrg(organizationId: string) {
  return await prisma.abiJob.findMany({
    where: {
      organizationId,
    },
  });
}

export async function reQueueJob(jobId: string) {
  return await prisma.abiJob.update({
    where: {
      id: jobId,
    },
    data: {
      status: ABIJOB_STATUS.CREATED,
    },
  });
}

export async function fetchAllPendingOrRunningForOrg(organizationId: string) {
  return await prisma.abiJob.findMany({
    where: {
      organizationId,
      OR: [
        {
          status: ABIJOB_STATUS.CREATED,
        },
        {
          status: ABIJOB_STATUS.RUNNING,
        },
      ],
    },
  });
}

export async function fetchPendingOrRunningForBranch(
  orgName: string,
  repoName: string,
  branch: string
) {
  return await prisma.abiJob.findFirst({
    where: {
      orgName,
      repoName,
      branch,
      OR: [
        {
          status: ABIJOB_STATUS.CREATED,
        },
        {
          status: ABIJOB_STATUS.RUNNING,
        },
      ],
    },
  });
}

export async function fetchAllQueuedAbiJobs() {
  return await prisma.abiJob.findMany({
    where: { status: ABIJOB_STATUS.CREATED },
  });
}

async function fetchNextQueuedAbiJob() {
  const oldestJob = await prisma.abiJob.findFirst({
    where: {
      status: ABIJOB_STATUS.CREATED,
    },
    orderBy: {
      updatedAt: "asc",
    },
  });

  if (oldestJob) {
    // Update the Abi Job so worker doesn't get stuck forever on this specific job
    await prisma.abiJob.update({
      where: {
        id: oldestJob.id,
      },
      data: {
        status: ABIJOB_STATUS.CREATED,
      },
    });
  }

  return oldestJob;
}

// Update abijob status
async function setAbiJobToStatus(id: string, status: ABIJOB_STATUS) {
  await prisma.abiJob.update({
    where: { id },
    data: {
      status,
    },
  });
}

export async function addAnAbiJob(newJob: AbiJobInput) {
  return await prisma.abiJob.create({
    data: {
      ...newJob,
    },
  });
}

// To check job status
export async function fetchOneAbiJobWithOrg(jobId: string, orgId: string) {
  // NOTE: Returns null if not found
  return await prisma.abiJob.findUnique({
    where: { id: jobId, organizationId: orgId },
  });
}
export async function fetchOneAbiJob(jobId: string) {
  // NOTE: Returns null if not found
  return await prisma.abiJob.findUnique({ where: { id: jobId } });
}

async function doTests() {
  // await addAnAbiJob({
  //   orgName: "GalloDaSballo",
  //   repoName: "twap-study",
  //   branch: "main",
  //   status: "created",
  // });
  // await fetchAllQueuedAbiJobs();
  // await findAndProcessAbiJobs();
  // await fetchAllAbiJobs();
  const allAbiData = await fetchPendingOrRunningForBranch(
    "GalloDaSballo",
    "twap-study",
    "main"
  );
  console.log("allAbiData", allAbiData);
}

// doTests();

// If there's a job

// TODO: Change the code in builder to use our new format?

// Build the repo

// We get a queue of all jobs at this time
// We always update each job from `created` -> `running` -> `completed`

// TODO:
/**
 * To add authentication
 * https://docs.github.com/en/rest/apps/apps?apiVersion=2022-11-28#get-a-repository-installation-for-the-authenticated-app
 * This one finds the token you need
 */

// We always run when we receive a job (by directly calling this)
// We also have a 10 minute cron, after which we check if we have jobs
export async function findAndProcessAbiJobs() {
  let newJob = await fetchNextQueuedAbiJob();
  while (newJob != null) {
    // Continue
    // Update the

    await setAbiJobToStatus(newJob.id, ABIJOB_STATUS.RUNNING);
    console.log("Running", newJob.id);

    const { orgName, repoName, branch, out, directory, organizationId } =
      newJob;
    try {
      // NOTE: This can throw!
      const { url, token } = await getCloneUrlAndToken(orgName, repoName);

      // First Promise
      // Build ABI and fetch GH Commit info
      // TODO: Permissions here
      // Given User that started / whose permissions are assigned
      // Get the View only Token for the Repo
      // NOTE: We have it in permissions
      const abiDataRequest = buildAndReturnABI(url, out, branch, directory);

      // TODO: This should be getLatestCommit
      // If the repo is public then this is fine
      // But if the repo is private, we need to generate the token
      const commitHashRequest = getLatestCommitForRepo(
        orgName,
        repoName,
        branch,
        token ? token : undefined // Optional param
      );

      const abiData = await abiDataRequest;
      const commitHash = await commitHashRequest;

      // NOTE: Refactoring to speed up, only once we're confident in the code
      // const [abiData, commitHash] = await Promise.all([
      //   abiDataRequest,
      //   commitHashRequest,
      // ]);

      // Store abi data to the user
      await createNewAbiData(
        orgName,
        repoName,
        branch,
        commitHash,
        JSON.stringify(abiData),
        organizationId
      );

      // TODO: if 2 users request the same repo, we can just replicate here
      // Cause we have done authentication at enqueuing
      // We could also limit for Public Repos, that prob is the move

      // Set job as complete
      await setAbiJobToStatus(newJob.id, ABIJOB_STATUS.COMPLETED);

      //TODO: A second Promise.all here, but let's make sure this works first
    } catch (e) {
      setAbiJobToStatus(newJob.id, ABIJOB_STATUS.ERRORED);

      console.log("Error in Running job", e);
    }

    // Update the ABI DATA

    // DONE (or webhook, but I don't think we need it)

    newJob = await fetchNextQueuedAbiJob();
  }
  // At the end here, we call ourselves, one more time to restart
}
