import { WEBHOOK_TYPE } from "@prisma/client";
import prisma from "./client";

// TODO: Add Pruning, any event of last X days should be auto-deleted, we don't need them

export async function fetchAllWebhooks() {
  return await prisma.webhookJob.findMany({
    orderBy: {
      createdAt: "desc",
    },
  });
}
export async function fetchLastFivewebhookJobs(organizationId: string) {
  return await prisma.webhookJob.findMany({
    where: {
      organizationId,
    },
    orderBy: {
      createdAt: "desc",
    },
    take: 5,
  });
}

export async function fetchLastTenWebhookJobsByRepo(
  organizationId: string,
  orgName: string,
  repoName: string
) {
  return await prisma.webhookJob.findMany({
    where: {
      organizationId,
      orgName,
      repoName,
    },
    orderBy: {
      createdAt: "desc",
    },
    take: 10,
  });
}

export async function createNewWebhookJob(
  organizationId: string,
  type: WEBHOOK_TYPE,
  orgName: string,
  repoName: string,
  ref: string
) {
  return await prisma.webhookJob.create({
    data: {
      organizationId,
      type,
      orgName,
      repoName,
      ref,
    },
  });
}
