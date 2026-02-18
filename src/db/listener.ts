import prisma from "./client";

export async function createListener(orgId: string) {
  return await prisma.listener.create({
    data: { 
      organizationId: orgId,
      enabled: true
    },
  });
}

export async function fetchAllOrgListeners() {
  // Find all Org Listeners, since we delete them on success
  return await prisma.listener.findMany({
    where: {},
    orderBy: {
      createdAt: "desc", // Latest by definition
    },
  });
}

// Given org ID find
export async function fetchListenerForOrg(orgId: string) {
  // Find all Org invites, since we delete them on success
  return await prisma.listener.findMany({
    where: { organizationId: orgId },
  });
}

// Given org ID find
export async function fetchListener(listenerId: string) {
  // Find all Org invites, since we delete them on success
  return await prisma.listener.findFirstOrThrow({
    where: { id: listenerId },
  });
}

export async function deleteOrgListener(listenerId: string) {
  await prisma.listener.delete({
    where: {
      id: listenerId,
    },
  });
}
