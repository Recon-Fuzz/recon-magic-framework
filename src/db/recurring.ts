import { createAlertFromRecurringJobId } from "./alerts";
import prisma from "./client";
import { log } from "./jobs";

export async function unsafeDeleteOneRecurringJob(recurringJobId: string) {
  return await prisma.$transaction([
    prisma.alert.deleteMany({
      where: {
        recurringJobId,
      },
    }),
    prisma.recurringJob.delete({
      where: {
        id: recurringJobId,
      },
    }),
  ]);
}
export async function unsafeCreateRecurringJobs(
  organizationId: string,
  recipeId: string,
  label: string,
  frequencyInSeconds: number
) {
  // NOTE: for safe you must ensure Recipe belongs to the orgId

  // TODO: May need to add some sort of validation for the recipe + job to ensure it can be recurring
  // e.g. need branch etc...

  return await prisma.recurringJob.create({
    data: {
      organizationId,
      recipeId,
      label,
      frequencyInSeconds,
    },
  });
}

// TODO: Jobs created by the recurringJob need to have the extra data of the recurring JobId

// Super get all
export async function unsafeFetchAllRecurringJobs() {
  return await prisma.recurringJob.findMany({
    where: {},
    orderBy: { updatedAt: "desc" },
  });
}

// Get all for ORG
export async function fetchAllRecurringJobs(organizationId: string) {
  return await prisma.recurringJob.findMany({
    where: {
      organizationId,
    },
    include: {
      alerts: true,
      // TODO 0XSI - Uncomment if we want to set alerts by broken properties
      // jobs: {
      //   include: {
      //     brokenProperties: true,
      //   }
      // },
    },
    orderBy: { updatedAt: "desc" },
  });
}

export async function toggleRecurringJob(
  organizationId: string,
  recurringJobId: string,
) {
  const foundRecurringJob = await prisma.recurringJob.findFirstOrThrow({
    where: {
      organizationId,
      id: recurringJobId,
    },
  });
  if (!foundRecurringJob) {
    throw new Error("Recurring Job not found");
  }
  return await prisma.recurringJob.update({
    where: {
      id: recurringJobId,
    },
    data: {
      enabled: !foundRecurringJob.enabled,
    },
  });
}

// Get All jobs for one
export async function fetchAllJobsGivenRecurringJob(
  organizationId: string,
  recurringJobId: string
) {
  // NOTE: See: https://www.prisma.io/docs/orm/reference/prisma-client-reference#include
  const recurringWithJobs = await prisma.recurringJob.findFirstOrThrow({
    where: {
      organizationId,
      id: recurringJobId,
    },
    include: {
      jobs: {
        orderBy: {
          updatedAt: "desc",
        },
      },
    },
    orderBy: { updatedAt: "desc" },
  });

  recurringWithJobs.jobs = recurringWithJobs.jobs.map((job) => log(job));

  return recurringWithJobs;
}

export const createAlertForRecurringJobs = async (
  recurringJobId: string,
  threshold: number,
  webhookUrl: string,
  orgId: string,
  telegramUsername: string,
  chatId: number
) => {
  try {
    const existingRecurringJob = await prisma.recurringJob.findFirstOrThrow({
      where: {
        id: recurringJobId,
        organizationId: orgId,
      },
    });
    if (!existingRecurringJob) {
      throw new Error("Recurring Job not found");
    } else {
      await createAlertFromRecurringJobId(recurringJobId, threshold, webhookUrl, telegramUsername, chatId);
    }
  } catch (err) {
    console.log(err);
    throw new Error("Failed to create alert");
  }
};

export const superCreateAlertForRecurringJobs = async (
  recurringJobId: string,
  threshold: number,
  webhookUrl: string,
) => {
  try {
    await createAlertFromRecurringJobId(recurringJobId, threshold, webhookUrl);
  } catch (err) {
    console.log(err);
    throw new Error("Failed to create alert");
  }
};
