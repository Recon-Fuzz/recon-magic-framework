import { Request, Response } from "express";
import express from "express";
import {
  onlyLoggedIn,
  orgCheck,
  requireProOrg,
  requireSuperAdmin,
} from "../middleware/auth";
import {
  createCampaign,
  deleteCampaign,
  fetchCampaigns,
  toggleCampaingsComments,
} from "../db/campaigns";
import { fetchOrgRecipes } from "../db/recipes";
import { sanitizeInput } from "../middleware/sanitizer";

const router = express.Router();
export default router;

router.get(
  "/",
  onlyLoggedIn,
  requireProOrg,
  orgCheck,
  async (req: Request, res: Response) => {
    const campaigns = await fetchCampaigns(req.user.userData!.organizationId);

    // TODO: We prob want to get at least the recipe IDs, probably the whole thing tbh

    return res.json({
      message: "All Campaigns for your Org",
      data: campaigns,
    });
  }
);

// NOTE: These are defaults for now given what is implemented
// TODO: Change these over time
// TODO: Campaign Types
async function sanitizedAndMakeDefaults(body: Request["body"], orgId: string) {
  const {
    displayName, // Can be empty string
    orgNames,
    repoNames,
    branchNames,
    recipeIds,
  } = body;

  // Given each recipeID
  // Fetch the recipe
  // Validate that the recipe belongs to the orgId
  const orgRecipes = await fetchOrgRecipes(orgId);
  const idsFromOrg = orgRecipes.map((recipe) => recipe.id);

  const validRecipes: String[] = recipeIds.filter((id: String | number) =>
    idsFromOrg.includes(String(id))
  );

  if (validRecipes.length === 0) {
    throw new Error("Recipes do not belong to the Organization");
  }

  let filteredRecipes = orgRecipes.filter((recipe) =>
    validRecipes.includes(recipe.id)
  );

  // recipes.connect{id}[]

  const recipes = {
    connect: filteredRecipes.map((entry) => {
      return {
        id: entry.id,
      };
    }),
  };

  // NOTE: These are all defaults
  // TODO: As we add support for more options, expand this
  const type = "COMMIT";
  const policy = "IGNORE";
  const checkInitiator = false;
  const initiatorIds: number[] = [];

  const checkOrgName = "MATCH_EXACT";
  const checkRepoName = "MATCH_EXACT";
  const checkBranchName = "MATCH_EXACT";

  return {
    displayName,
    orgNames,
    repoNames,
    branchNames,

    type,
    policy,
    checkInitiator,
    initiatorIds,

    recipes, // TODO Need to add this I think

    checkOrgName,
    checkRepoName,
    checkBranchName,
  };
}

// NOTE: Temporary, also safe since Super Admin
router.post(
  "/super",
  requireSuperAdmin,
  sanitizeInput,
  async (req: Request, res: Response) => {
    const { organizationId } = req.body;

    // TODO: Especially population of Recipes MUST be sanitized
    const sanitizedData = await sanitizedAndMakeDefaults(
      req.body,
      organizationId
    );

    const newCampaign = await createCampaign(organizationId, sanitizedData);

    return res.json({
      message: "Created Campaign",
      data: newCampaign,
    });
  }
);

router.post(
  "/",
  onlyLoggedIn,
  requireProOrg,
  orgCheck,
  sanitizeInput,
  async (req: Request, res: Response) => {
    // TODO: Especially population of Recipes MUST be sanitized
    const sanitizedData = await sanitizedAndMakeDefaults(
      req.body,
      req.user.userData!.organizationId
    );

    const newCampaign = await createCampaign(
      req.user.userData!.organizationId,
      sanitizedData
    );

    return res.json({
      message: "Created Campaign",
      data: newCampaign,
    });
  }
);

router.put(
  "/togglecomments/:campaignId",
  onlyLoggedIn,
  requireProOrg,
  orgCheck,
  sanitizeInput,
  async (req: Request, res: Response) => {
    const { campaignId } = req.params;
    const { comments } = req.body;

    const orgId = req.user.userData!.organizationId;
    const updatedCampaign = await toggleCampaingsComments(
      campaignId,
      comments,
      orgId,
    );

    return res.json({
      message: "Updated Campaign",
      data: updatedCampaign,
    });
  }
);

router.delete(
  "/:campaignId",
  onlyLoggedIn,
  requireProOrg,
  orgCheck,
  sanitizeInput,
  async (req: Request, res: Response) => {
    const { campaignId } = req.params;

    const deletedCampaign = await deleteCampaign(
      req.user.userData!.organizationId,
      campaignId
    );

    return res.json({
      message: "Deleted Campaign",
      data: deletedCampaign,
    });
  }
);
