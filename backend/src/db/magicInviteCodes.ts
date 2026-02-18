import { v4 as uuidv4 } from "uuid";
import prisma from "./client";

// Create a magic invite code with auto-generated UUID code
export async function createMagicInviteCode(adminId: string) {
  const code = uuidv4();
  return await prisma.magicInviteCode.create({
    data: {
      code,
      createdBy: adminId,
    },
  });
}

// Create a magic invite code with custom memorable code
export async function createMagicInviteCodeCustom(
  customCode: string,
  adminId: string
) {
  return await prisma.magicInviteCode.create({
    data: {
      code: customCode,
      createdBy: adminId,
    },
  });
}

// Get a magic invite code by its code string
export async function getMagicInviteCodeByCode(code: string) {
  return await prisma.magicInviteCode.findUnique({
    where: { code },
  });
}

// List all magic invite codes (for super admin)
export async function listMagicInviteCodes() {
  return await prisma.magicInviteCode.findMany({
    orderBy: { createdAt: "desc" },
    include: {
      redeemedByOrg: {
        select: { id: true, name: true },
      },
    },
  });
}

// Delete an unused magic invite code
export async function deleteMagicInviteCode(code: string) {
  const existing = await prisma.magicInviteCode.findUnique({
    where: { code },
  });

  if (!existing) {
    throw new Error("Code not found");
  }

  if (existing.redeemedByOrgId) {
    throw new Error("Cannot delete a redeemed code");
  }

  return await prisma.magicInviteCode.delete({
    where: { code },
  });
}

// Redeem a magic invite code for an organization
// Returns the updated org with new credit count
export async function redeemMagicInviteCode(code: string, orgId: string) {
  // Check if org already redeemed a code
  const org = await prisma.organization.findUnique({
    where: { id: orgId },
    include: { redeemedInviteCode: true },
  });

  if (!org) {
    throw new Error("Organization not found");
  }

  if (org.redeemedInviteCode) {
    throw new Error("Organization has already redeemed an invite code");
  }

  // Check if code exists and is not redeemed
  const inviteCode = await prisma.magicInviteCode.findUnique({
    where: { code },
  });

  if (!inviteCode) {
    throw new Error("Invalid invite code");
  }

  if (inviteCode.redeemedByOrgId) {
    throw new Error("Code has already been redeemed");
  }

  // Redeem: update code and increment org credits in a transaction
  const [updatedCode, updatedOrg] = await prisma.$transaction([
    prisma.magicInviteCode.update({
      where: { code },
      data: {
        redeemedAt: new Date(),
        redeemedByOrgId: orgId,
      },
    }),
    prisma.organization.update({
      where: { id: orgId },
      data: {
        magicCredits: { increment: 1 },
      },
    }),
  ]);

  return { code: updatedCode, org: updatedOrg };
}
