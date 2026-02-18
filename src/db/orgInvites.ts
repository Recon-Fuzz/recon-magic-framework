import prisma from "./client";

export async function createInviteToOrg(orgId: string) {
  return await prisma.orgInvite.create({
    data: { organizationId: orgId },
  });
}

export async function fetchAllOrgInvites() {
  // Find all Org invites, since we delete them on success
  return await prisma.orgInvite.findMany({
    where: {},
    orderBy: {
      createdAt: "desc", // Latest by definition
    },
  });
}

// Given org ID find
export async function fetchOrgInvitesForOrg(orgId: string) {
  // Find all Org invites, since we delete them on success
  return await prisma.orgInvite.findMany({
    where: { organizationId: orgId },
  });
}

// Given a inviteId, use it and attach github user to a org
// NOTE: Re-creating the user will fail so this should be used only the first time
// NOTE: Because of this we can consider a user without a Org
// As a user that cannot do some stuff, e.g. they cannot push jobs
// Returns the orgId to add the user to
// Throws if it fails
export async function useOrgInvite(inviteId: string): Promise<string> {
  // Delete the Invite and keep the data
  const { organizationId } = await prisma.orgInvite.delete({
    where: {
      id: inviteId,
    },
  });

  // Org auto updates once the user is created
  return organizationId;
}

export async function deleteOrgInvite(inviteId: string) {
  await prisma.orgInvite.delete({
    where: {
      id: inviteId,
    },
  });
}
