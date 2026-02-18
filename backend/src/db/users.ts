import prisma from "./client";
import { useOrgInvite } from "./orgInvites";
import { createFreeOrg, deleteOrganizationIfEmpty } from "./organizations";

// Create a new user with `githubUserId` belonging to `orgId` org
export async function createUser(githubUserId: string, orgId: string) {
  return await prisma.user.create({
    data: {
      organizationId: orgId,
      id: githubUserId,
    },
  });
}

// Given a GH ID and OrgName
// Create a new Free Org
// Then create a User
// NOTE: This is how free account can be created
// We would expect a few of these to have to migrate to another ORG
export async function createUserAndFreeOrg(
  githubUserId: string,
  orgName: string
) {
  // Assign user to a new Org (unpaid)
  // Create an org
  const { id } = await createFreeOrg(orgName);

  const newUser = await createUser(githubUserId, id);

  return newUser;
}

// Create user via org invite
export async function createUserFromOrgInvite(
  inviteId: string,
  githubUserId: string
) {
  const orgId = await useOrgInvite(inviteId);

  const newUser = await createUser(githubUserId, orgId);

  return newUser;
}

export async function deleteUserAndOrg(githubUserId: string) {
  const deletedUser = await prisma.user.delete({
    where: {
      id: githubUserId,
    },
  });

  const deletedOrg = await deleteOrganizationIfEmpty(
    deletedUser.organizationId
  );

  return {
    user: deletedUser,
    org: deletedOrg,
  };
}

// Given invite ID and User Id
// Consume the Invite
// Add user to new org
// Conditionally delete old org if it has no users left
export async function userUseInviteAndJoinId(
  inviteId: string,
  githubUserId: string
) {
  // TODO: Promise.all both
  const orgId = await useOrgInvite(inviteId);

  // Get old userData so we can check if we can delete the orgId
  const prevUserData = await getUserInfo(githubUserId);

  const res = await changeUserOrg(githubUserId, orgId);

  // NOTE: Cleanup the org
  // NOTE: We need to do it after due to race condition on DB relation
  // NOTE: `deleteOrganizationIfEmpty` throws so we know it will either delete on empty or fail
  if (prevUserData?.organizationId) {
    try {
      await deleteOrganizationIfEmpty(prevUserData.organizationId);
      console.info(
        "userUseInviteAndJoinId Delete org",
        prevUserData.organizationId
      );
    } catch (e) {
      console.info(
        "userUseInviteAndJoinId Did not delete org",
        prevUserData.organizationId
      );
    }
  }

  return res;
}

// Given githubUserId, Return the user info
export async function getAllUsers() {
  return await prisma.user.findMany({});
}
export async function getUserInfo(githubUserId: string) {
  return await prisma.user.findFirst({
    where: {
      id: githubUserId,
    },
  });
}

// Given the `githubUserId`, set a user to be in `newOrgId`
export async function changeUserOrg(githubUserId: string, newOrgId: string) {
  return await prisma.user.update({
    where: {
      id: githubUserId,
    },
    data: {
      organizationId: newOrgId,
    },
  });
}


export async function getUsersByOrganizationId(organizationId: string) {
  return await prisma.user.findMany({
    where: {
      organizationId: organizationId,
    },
  });
}