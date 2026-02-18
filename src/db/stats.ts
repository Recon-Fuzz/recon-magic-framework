import prisma from "./client";

export async function getCounts() {
  const [userCount, abiJobCount, abiDataCount, organizationCount, jobCount, brokenPropertyCount] =
    await prisma.$transaction([
      prisma.user.count({}),
      prisma.abiJob.count({}),
      prisma.aBIData.count({}),
      prisma.organization.count({}),
      prisma.job.count({}),
      prisma.brokenProperty.count({}),
    ]);
  return {
    userCount,
    abiJobCount,
    abiDataCount,
    organizationCount,
    jobCount,
    brokenPropertyCount,
  };
}
