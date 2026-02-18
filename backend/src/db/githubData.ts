import prisma from "./client";

export const getGHdataByJobId = async (jobId: string) => {
  return await prisma.githubData.findFirst({
    where: {
      jobId: jobId,
    },
    include: {
      campaign: true,
    },
  });
}

export const createOrUpdateGHData = async(campaignId: string, orgName: string, repoName: string, branchName: string, issueId: number, installationId: number, jobId: string) => {
  // Check if campaign exists
  const existingCampaign = await prisma.campaign.findUnique({
    where: { id: campaignId }
  });

  if (!existingCampaign) {
    throw new Error(`Campaign with id ${campaignId} does not exist`);
  }

  const foundGhData = await prisma.githubData.findFirst({
    where: {
      campaignId: campaignId,
      orgName: orgName,
      repoName: repoName,
      branchName: branchName,
      issueId: issueId,
      installationId: installationId,
      jobId: jobId,
    },
  });

  if (foundGhData) {
    return foundGhData;
  } else {
    console.log("No GH data found ... updating");
    return await prisma.githubData.create({
      data: {
        campaignId: campaignId,
        orgName: orgName,
        repoName: repoName,
        branchName: branchName,
        issueId: issueId,
        installationId: installationId,
        jobId: jobId,
      },
    });
  }
}

export const getGhDataFromCampaign = async (orgId:string) => {
  return await prisma.campaign.findMany({
    where: {
      organizationId: orgId,
    },
    include: {
      githubData: true,
    },
  });
}
