import { Request, Response } from "express";

import express from "express";
import { requireSuperAdmin } from "../../middleware/auth";
import {
  createNewRecipeUnsafe,
  deleteRecipeUnsafe,
  unsafeFetchAllRecipes,
  updateRecipeUnsafe,
} from "../../db/recipes";

const router = express.Router();
export default router;

// Get all recipes for all users
router.get("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const recipes = await unsafeFetchAllRecipes();

  return res.json({
    message: "All recipes in the system",
    data: recipes,
  });
});

// Create Recipe for any org
router.post("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const created = await createNewRecipeUnsafe(req.body);

  return res.json({
    message: `Created ${created.id}`,
    data: created,
  });
});

// Delete a Recipe
router.delete(
  "/:recipeId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { recipeId } = req.params;

    const deleted = await deleteRecipeUnsafe(recipeId);

    return res.json({
      message: `Deleted ${deleted.id}`,
      data: deleted,
    });
  }
);

// Update a Recipe
router.put(
  "/:recipeId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { recipeId } = req.params;
    const { recipeData } = req.body;

    const deleted = await updateRecipeUnsafe(recipeId, recipeData);

    return res.json({
      message: `Updated ${deleted.id}`,
      data: deleted,
    });
  }
);
