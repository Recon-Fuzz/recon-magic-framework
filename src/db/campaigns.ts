import { Recipe, STRING_MATCH_POLICY } from "@prisma/client";
import prisma from "./client";

export async function unsafeFetchAllCampaigns() {
  return await prisma.campaign.findMany({
    include: {
      recipes: true,
    },
    orderBy: {
      updatedAt: "desc",
    },
  });
}

// Fetch
export async function fetchCampaigns(organizationId: string) {
  return await prisma.campaign.findMany({
    where: {
      organizationId,
    },
    include: {
      recipes: {
        include: {
          alerts: true,
        },
      },
    },
    orderBy: {
      updatedAt: "desc",
    },
  });
}

// Given the webhook data, check if we have a campaign to trigger
// TODO: Filtering MUST be Unit Tested
export async function fetchCampaignsByWebhookData(
  orgName: string,
  repoName: string,
  ref: string, // Is actually the branch
  initiator: number
) {
  const found = await prisma.campaign.findMany({
    where: {
      // Instead of searching by orgID, which would be the person creating the campaign
      // we search for the target repos for this campaign
      // with more filtering done below
      orgNames: {
        has: orgName,
      },
      // The organization relation is used to check if the owning org has PAID status
      organization: {
        billingStatus: "PAID",
      },
    },
    include: {
      recipes: true,
    },
  });

  // Check for inclusion via match rules manually
  let foundCampaigns = found.filter((campaign) => {
    // For every campaign make sure who can initiate it
    // If initiating is not open AND the initiator is not on the list then we return false
    if (
      campaign.checkInitiator == true &&
      !campaign.initiatorIds.includes(initiator)
    ) {
      return false;
    }

    // Apply all matching rules
    // NOTE: Currently we only implement match exact to return false
    if (campaign.checkOrgName == STRING_MATCH_POLICY.MATCH_EXACT) {
      if (!campaign.orgNames.includes(orgName)) {
        return false;
      }
    }

    if (campaign.checkRepoName == STRING_MATCH_POLICY.MATCH_EXACT) {
      if (!campaign.repoNames.includes(repoName)) {
        return false;
      }
    }

    if (campaign.checkBranchName == STRING_MATCH_POLICY.MATCH_EXACT) {
      if (!campaign.branchNames.includes(ref)) {
        return false;
      }
    }

    return true;
  });

  return foundCampaigns;
}

export async function unsafeCreateCampaign(data: any) {
  return await prisma.campaign.create({
    data: {
      ...data,
    },
  });
}

/// Throws if invalid
/// TODO: Is this how you populate many to many?
// TODO: not sure if we need this
async function validateOrganizationIdAndRecipes(
  organizationId: string,
  recipes: Recipe[]
) {
  //TODO 0XSI - WRONG !
  return; // TODO: Add the check!!!
  await Promise.all(
    await recipes.map(async (recipe: Recipe) => {
      // Fetch recipe
      // Ensure it belongs to orgId
      const foundRecipe = await prisma.recipe.findFirstOrThrow({
        where: {
          id: recipe.id,
        },
      });

      if (foundRecipe.organizationId != organizationId) {
        throw new Error("Organization Mismatch");
      }

      return foundRecipe;
    })
  );
}

export async function createCampaign(organizationId: string, data: any) {
  // TODO: Sanitize each recipe
  // Each recipe must belong to the right orgId
  // TODO: Should prob sanitize this everywhere
  await validateOrganizationIdAndRecipes(organizationId, data.recipes);

  return await prisma.campaign.create({
    data: {
      ...data,
      organizationId,
    },
  });
}

export async function deleteCampaign(organizationId: string, id: string) {
  return await prisma.campaign.delete({
    where: {
      organizationId,
      id,
    },
  });
}

export async function unsafeDeleteCampaign(id: string) {
  return await prisma.campaign.delete({
    where: {
      id,
    },
  });
}

// TODO: How is this supposed to be done to be safe?
export async function unsafeUpdateCampaign(id: string, campaignData: any) {
  return await prisma.campaign.update({
    where: {
      id,
    },
    data: campaignData,
  });
}

export async function updateCampaign(
  id: string,
  organizationId: string,
  campaignData: any
) {
  return await prisma.campaign.update({
    where: {
      id,
      organizationId,
    },
    data: campaignData,
  });
}

export const toggleCampaingsComments = async (
  id: string,
  value: boolean,
  orgId: string
) => {
  await prisma.campaign.update({
    where: {
      id,
      organizationId: orgId,
    },
    data: {
      comments: value,
    },
  });
};
