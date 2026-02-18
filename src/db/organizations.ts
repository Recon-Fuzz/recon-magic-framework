import { BILLING_STATUS } from "@prisma/client";
import prisma from "./client";

// Create an empty org
export async function createFreeOrg(name: string) {
  return await prisma.organization.create({
    data: {
      name: name,
      billingStatus: BILLING_STATUS.UNPAID,
    },
  });
}

// TODO: SUPER ADMIN
// WE CAN CREATE AN ORG THAT IS PREPAID
export async function getAllOrgs() {
  return await prisma.organization.findMany({
    include:{
      users: true
    }
  });
}

export async function getOrganization(orgId: string) {
  return await prisma.organization.findFirst({
    where: {
      id: orgId,
    },
  });
}

// Org names are unique on Github
export async function getOrgByName(orgName: string) {
  return await prisma.organization.findFirstOrThrow({
    where: {
      name: orgName
    }
  })
}

export async function giveTrialOrg(orgId: string) {
  return await prisma.organization.update({
    data: {
      billingStatus: BILLING_STATUS.TRIAL,
      // TODO: when would billing expire?
      billingUpdateAt: new Date(
        new Date().getTime() + 1000 * 30 * 60 * 60 * 24 // 30 days
      ),
    },
    where: {
      id: orgId,
    },
  });
}

export async function giveProToOrg(orgId: string) {
  return await prisma.organization.update({
    data: {
      billingStatus: BILLING_STATUS.PAID,
      // TODO: when would billing expire?
      billingUpdateAt: new Date(
        new Date().getTime() + 1000 * 30 * 60 * 60 * 24 // 30 days
      ),
    },
    where: {
      id: orgId,
    },
  });
}
export async function removeProFromOrg(orgId: string) {
  return await prisma.organization.update({
    data: {
      billingStatus: BILLING_STATUS.UNPAID,
      billingUpdateAt: new Date(new Date().getTime()),
    },
    where: {
      id: orgId,
    },
  });
}

export async function setMinutesToOrg(orgId: string, minutesToAdd: number) {
  return await prisma.organization.update({
    data: {
      totalMinutesLeft: minutesToAdd,
    },
    where: {
      id: orgId,
    },
  });
}

export async function renameOrganization(orgId: string, newName: string) {
  return await prisma.organization.update({
    data: {
      name: newName,
    },
    where: {
      id: orgId,
    },
  });
}

export async function deleteOrganizationIfEmpty(orgId: string) {
  // Check that it has no users
  const users = await prisma.user.findMany({
    where: {
      organizationId: orgId,
    },
  });

  if (users.length > 0) {
    console.log("Org has users", users);
    console.log("Not deleting");
    return null;
  }

  // Delete
  return await prisma.organization.delete({
    where: {
      id: orgId,
    },
  });
}
