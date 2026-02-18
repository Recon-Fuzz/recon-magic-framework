import prisma from "./client";

// Get an organization's magic credit balance
export async function getOrgMagicCredits(orgId: string) {
  const org = await prisma.organization.findUnique({
    where: { id: orgId },
    select: { magicCredits: true },
  });

  return org?.magicCredits ?? 0;
}

// Decrement an organization's magic credits by 1
// Returns the new credit count
export async function decrementOrgMagicCredit(orgId: string) {
  const org = await prisma.organization.findUnique({
    where: { id: orgId },
    select: { magicCredits: true },
  });

  if (!org || org.magicCredits < 1) {
    throw new Error("No magic credits available");
  }

  const updated = await prisma.organization.update({
    where: { id: orgId },
    data: {
      magicCredits: { decrement: 1 },
    },
  });

  return updated.magicCredits;
}

// Grant an organization +1 magic credit (super admin only)
export async function grantOrgMagicCredit(orgId: string) {
  const updated = await prisma.organization.update({
    where: { id: orgId },
    data: {
      magicCredits: { increment: 1 },
    },
  });

  return updated.magicCredits;
}

// Check if an organization has already redeemed a code
export async function hasOrgRedeemedCode(orgId: string) {
  const org = await prisma.organization.findUnique({
    where: { id: orgId },
    include: { redeemedInviteCode: true },
  });

  return !!org?.redeemedInviteCode;
}
