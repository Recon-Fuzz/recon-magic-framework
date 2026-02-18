import prisma from "./client";

// Fetch all for Org
export async function fetchAllShares() {
  return await prisma.share.findMany({});
}

export async function fetchAllSharesForOrg(organizationId: string) {
  return await prisma.share.findMany({
    where: {
      organizationId,
    },
    include: {
      job: true,
    }
  });
}

// Fetch one for Org
export async function fetchOneShare(shareId: string) {
  return await prisma.share.findFirst({
    where: {
      id: shareId,
    },
    include: {
      job: true,
    }
  });
}

// Create new Share for given Org and Job id
export async function createNewShare(organizationId: string, jobId: string) {
  return await prisma.share.create({
    data: {
      organizationId,
      jobId,
    },
  });
}

// Delete new Share for given orgId
export async function deleteShareForOrg(
  organizationId: string,
  shareId: string
) {
  return await prisma.share.delete({
    where: {
      organizationId,
      id: shareId,
    },
  });
}

export async function deleteShare(shareId: string) {
  return await prisma.share.delete({
    where: {
      id: shareId,
    },
  });
}
