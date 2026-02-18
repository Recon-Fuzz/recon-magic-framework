import { ABIJOB_STATUS, FUZZER } from "@prisma/client";

export interface AbiJobInput {
  orgName: string;
  repoName: string;
  branch: string;
  directory: string;
  out: string;
  status: ABIJOB_STATUS;
  organizationId: string;
}

export interface RunnableJob {
  // Repo Data
  orgName: string;
  repoName: string;
  ref: string;

  // Minimal Runner info
  fuzzer: FUZZER;

  // Org Data
  organizationId: string;

  // Optional Fields
  directory?: string;
  preprocess?: string;
  duration?: number;
  arbitraryCommand?: string;
  fuzzerArgs?: string;
  label?: string;
  recipeId: string;
}
