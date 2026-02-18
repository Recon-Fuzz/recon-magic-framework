import { Request, Response } from "express";
import express from "express";
import { onlyLoggedIn, requireProOrg, orgCheck } from "../middleware/auth";
import {
  createNewRecipeSafe,
  deleteRecipeWithOrg,
  fetchOrgRecipes,
  fetchOrgRecipesWithOrgName,
  fetchOrgRecipesWithRepoName,
  updateRecipeWithOrg,
} from "../db/recipes";
import { sanitizeInput } from "../middleware/sanitizer";

const router = express.Router();
export default router;
// Get all my recipes
router.get("/", onlyLoggedIn, orgCheck, async (req: Request, res: Response) => {
  const recipes = await fetchOrgRecipes(req.user.userData!.organizationId);

  return res.json({
    message: "All recipes for your org",
    data: recipes,
  });
});

// Get all my recipes with OrgName
router.get(
  "/orgName/:orgName",
  onlyLoggedIn,
  orgCheck,
  sanitizeInput,
  async (req: Request, res: Response) => {
    const { orgName } = req.params;

    const recipes = await fetchOrgRecipesWithOrgName(
      req.user.userData!.organizationId,
      orgName
    );

    return res.json({
      message: `All recipes for your org with GH org: ${orgName}`,
      data: recipes,
    });
  }
);

// Get all my recipes with OrgName
router.get(
  "/repoName/:repoName",
  onlyLoggedIn,
  orgCheck,
  sanitizeInput,
  async (req: Request, res: Response) => {
    const { repoName } = req.params;

    const recipes = await fetchOrgRecipesWithRepoName(
      req.user.userData!.organizationId,
      repoName
    );

    return res.json({
      message: `All recipes for your org for repo: ${repoName}`,
      data: recipes,
    });
  }
);

// Create Recipe
router.post(
  "/",
  onlyLoggedIn,
  orgCheck,
  requireProOrg,
  sanitizeInput,
  async (req: Request, res: Response) => {
    const body = req.body;
    if (body.displayName === "") {
      res.status(400);
      return res.json({ message: "displayName cannot be empty", data: {} });
    }
    try {
      const created = await createNewRecipeSafe(
        req.user.userData!.organizationId,
        req.body
      );
      if (!created) {
        res.status(400);
        return res.json({ message: "Error creating recipe", data: {} });
      }
      return res.json({
        message: `Created ${created.id}`,
        data: created,
      });
    } catch (error) {
      console.error("error creating recipe:", error);
      res.status(500);
      return res.json({ message: "Error creating recipe", data: {} });
    }
  }
);

// Delete a Recipe
router.delete(
  "/:recipeId",
  onlyLoggedIn,
  orgCheck,
  sanitizeInput,
  async (req: Request, res: Response) => {
    const { recipeId } = req.params;

    try {
      const deleted = await deleteRecipeWithOrg(
        req.user.userData!.organizationId,
        recipeId
      );
      if (!deleted) {
        res.status(400);
        return res.json({ message: "Error deleting recipe", data: {} });
      }
      return res.json({
        message: `Deleted ${deleted.id}`,
        data: deleted,
      });
    } catch (error) {
      res.status(500);
      return res.json({ message: "Error deleting recipe", data: {} });
    }
  }
);

// Update a Recipe
router.put(
  "/:recipeId",
  onlyLoggedIn,
  requireProOrg,
  orgCheck,
  sanitizeInput,
  async (req: Request, res: Response) => {
    const { recipeId } = req.params;
    const { recipeData } = req.body;

    try {
      const updated = await updateRecipeWithOrg(
        req.user.userData!.organizationId,
        recipeId,
        recipeData
      );
      if (!updated) {
        res.status(400);
        return res.json({ message: "Error updating recipe", data: {} });
      }
      return res.json({
        message: `Updated ${updated.id}`,
        data: updated,
      });
    } catch (error) {
      res.status(500);
      return res.json({ message: "Error updating recipe", data: {} });
    }
  }
);
