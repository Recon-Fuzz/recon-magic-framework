import { FUZZER, Recipe } from "@prisma/client";
import prisma from "./client";
import { sanitizePreprocess } from "../sanitizePreprocess";

// NOTE: Super admin fetch
export async function unsafeFetchAllRecipes() {
  return await prisma.recipe.findMany({
    where: {},
    orderBy: { updatedAt: "desc" },
    include: {
      alerts: true,
    },
  });
}
export async function fetchOrgRecipes(orgId: string) {
  return await prisma.recipe.findMany({
    where: { organizationId: orgId },
    orderBy: { updatedAt: "desc" },
    include: {
      alerts: true,
    },
  });
}

export async function fetchOrgRecipesWithOrgName(
  orgId: string,
  orgName: string
) {
  return await prisma.recipe.findMany({
    where: { organizationId: orgId, orgName },
    orderBy: { updatedAt: "desc" },
    include: {
      alerts: true,
    },
  });
}
export async function fetchOrgRecipesWithRepoName(
  orgId: string,
  repoName: string
) {
  return await prisma.recipe.findMany({
    where: { organizationId: orgId, repoName },
    orderBy: { updatedAt: "desc" },
    include: {
      alerts: true,
    },
  });
}

export interface RecipeInput {
  displayName: string;
  organizationId: string;

  // GH
  orgName?: string;
  repoName?: string;
  ref?: string;

  // Processing args
  fuzzer?: FUZZER;
  directory?: string;
  preprocess?: string;
  duration?: number;
  arbitraryCommand?: string;
  fuzzerArgs?: any;
}

// Safe as we'll enforce orgId in the calling function
export async function createNewRecipeSafe(
  orgId: string,
  recipeData: RecipeInput
) {
  // TODO 0XSI
  // Remove that after Corn engagement
  const isAllowedScript = orgId === "5a9d06f3-e597-4cb6-b07a-c045d5a6b03b";
  return await prisma.recipe.create({
    data: {
      ...recipeData,

      // NOTE: Explicitly sanitize preprocess
      preprocess: recipeData?.preprocess
        ? sanitizePreprocess(recipeData.preprocess, isAllowedScript)
        : null,
      arbitraryCommand: null,
      organizationId: orgId, /// NOTE: Important! To prevent overwriting via spread
    },
  });
}

// Allows to specify for any orgId
export async function createNewRecipeUnsafe(recipeData: RecipeInput) {
  return await prisma.recipe.create({
    data: {
      ...recipeData,
    },
  });
}

export async function deleteRecipeWithOrg(orgId: string, recipeId: string) {
  return await prisma.recipe.delete({
    where: {
      id: recipeId,
      organizationId: orgId,
    },
  });
}
export async function deleteRecipeUnsafe(recipeId: string) {
  return await prisma.recipe.delete({
    where: {
      id: recipeId,
    },
  });
}

// NOTE: Overrides any settings except organizationId so it's pretty arbitrary
export async function updateRecipeWithOrg(
  orgId: string,
  recipeId: string,
  recipeData: RecipeInput
) {
  // TODO 0XSI
  // Remove that after Corn engagement
  const isAllowedScript = orgId === "5a9d06f3-e597-4cb6-b07a-c045d5a6b03b";
  return await prisma.recipe.update({
    where: {
      id: recipeId,
      organizationId: orgId,
    },

    data: {
      ...recipeData,
      // NOTE: Explicitly sanitize preprocess
      preprocess: recipeData?.preprocess
        ? sanitizePreprocess(recipeData.preprocess, isAllowedScript)
        : null,
      arbitraryCommand: null,
      organizationId: orgId, /// NOTE: Important! To prevent overwriting via spread
    },
  });
}

// NOTE: This can be used to switch organizations!
export async function updateRecipeUnsafe(
  recipeId: string,
  recipeData: RecipeInput
) {
  return await prisma.recipe.update({
    where: {
      id: recipeId,
    },
    data: {
      ...recipeData,
    },
  });
}

export async function getRecipeById(recipeId: string) {
  return await prisma.recipe.findUnique({
    where: {
      id: recipeId,
    },
  });
}

export async function createRecipe(recipe: Recipe, prepareContracts: any, chainId?: number) {
  const { id, createdAt, updatedAt, ...cleanedRecipe } = recipe;
  let fuzzerArgs = recipe.fuzzerArgs as Record<string, any>;
  fuzzerArgs.prepareContracts = prepareContracts;
  fuzzerArgs.govFuzz = true;
  fuzzerArgs.forkMode = "TESTNET-SEPOLIA"; // TODO CHANGE THAT
  // Map to whatever the runner expects
  if (chainId) {
    switch (chainId) {
      case 1:
        fuzzerArgs.forkMode = "MAINNET";
        break;
      case 11155111:
        fuzzerArgs.forkMode = "TESTNET-SEPOLIA";
        break;
      case 5:
        fuzzerArgs.forkMode = "TESTNET-GOERLI";
        break;
      case 137:
        fuzzerArgs.forkMode = "POLYGON";
        break;
      case 42161:
        fuzzerArgs.forkMode = "ARBITRUM";
        break;
      case 10:
        fuzzerArgs.forkMode = "OPTIMISM";
        break;
      case 534352:
        fuzzerArgs.forkMode = "SCROLL";
        break;
      case 21000001:
        fuzzerArgs.forkMode = "TESTNET-CORN";
        break;
      case 21000000:
        fuzzerArgs.forkMode = "MAINNET-CORN";
        break;
      default:
        fuzzerArgs.forkMode = `TESTNET-${chainId}`;
        break;
    }
  }

  return await prisma.recipe.create({
    data: {
      ...cleanedRecipe,
      displayName: "Gov Fuzzing recipe",
      fuzzerArgs
    }
  });
}

export async function updateRecipeDisplayName(recipeId: string, displayName: string) {
  return await prisma.recipe.update({
    where: { id: recipeId },
    data: { displayName },
  });
}
