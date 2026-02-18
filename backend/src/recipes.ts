import { Recipe } from "@prisma/client";
import { RunnableJob } from "./types";

// Given inputs, recipe and a accessor key, get w/e is available, give prio to inputs and use recipe as fallback
// Used for optional fields
function orRecipe(inputs: any, recipe: Recipe, key: string): any {
  if (inputs[key]) {
    return inputs[key];
  }

  // @ts-ignore
  return recipe[key];
}

// Given inputs, recipe and a accessor key, get w/e is available, give prio to inputs and use recipe as fallback
// Throws if neither value is available
// Used for mandatory fields
function orRecipeRequired(inputs: any, recipe: Recipe, key: string): any {
  if (inputs[key]) {
    return inputs[key];
  }

  if (recipe[key as keyof Recipe]) {
    return recipe[key as keyof Recipe];
  }

  throw Error(`Missing key ${key}`);
}


// Given recipe and inputs make a job, using or rules
// TODO: Refactor to have recipe on the left since it's the default
export function makeJobFromRecipe(inputs: any, recipe: Recipe): RunnableJob {
  return {
    // NOTE: If recipe doesn't have this, then it must revert
    orgName: orRecipeRequired(inputs, recipe, "orgName"),
    repoName: orRecipeRequired(inputs, recipe, "repoName"),
    ref: orRecipeRequired(inputs, recipe, "ref"),

    fuzzer: orRecipeRequired(inputs, recipe, "fuzzer"),

    label: `[RECURRING]-${recipe.displayName}`,

    directory: orRecipe(inputs, recipe, "directory"),
    preprocess: orRecipe(inputs, recipe, "preprocess"),
    duration: orRecipe(inputs, recipe, "duration"),
    arbitraryCommand: orRecipe(inputs, recipe, "arbitraryCommand"),
    fuzzerArgs: orRecipe(inputs, recipe, "fuzzerArgs"),

    organizationId: recipe.organizationId,
    recipeId: recipe.id,

    // TODO: Should we add a way to share automatically?
  };
}

// Validate that job from recipe is a valid job
// NOTE: Fails in many edge cases, such as missing config file
export function isJobValid(input: any): boolean {
  const requiredFields = ['orgName', 'repoName', 'ref', 'fuzzer', 'organizationId'];

  return requiredFields.every(field => Boolean(input[field]));
}
