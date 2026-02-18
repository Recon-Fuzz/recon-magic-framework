import { makeAbiIdentifier } from "../utils";
import prisma from "./client";

// TODO: Handler for API response
// To see if we have the data already

export async function createNewAbiData(
  orgName: string,
  repoName: string,
  branch: string,
  commit: string,
  abiData: string,
  orgId: string
) {
  return await prisma.aBIData.create({
    data: {
      identifier: makeAbiIdentifier(orgName, repoName, branch),
      abiData: abiData,
      commit,
      organizationId: orgId, // NOTE: We attach the abi to an org
    },
  });
}

export async function deleteAbiData(abiDataId: string, orgId: string) {
  return await prisma.aBIData.delete({
    where: {
      id: abiDataId,
      organizationId: orgId,
    },
  });
}

export async function superDeleteAbiData(abiDataId: string) {
  return await prisma.aBIData.delete({
    where: {
      id: abiDataId,
    },
  });
}

export async function updateAbiData(
  abiDataId: string,
  commit: string,
  abiData: string
) {
  return await prisma.aBIData.update({
    data: {
      abiData: abiData,
      commit,
    },
    where: {
      id: abiDataId,
    },
  });
}

export async function fetchAllSystemAbiData() {
  return await prisma.aBIData.findMany({});
}

export async function fetchAllOrgAbiData(orgId: string) {
  return await prisma.aBIData.findMany({
    where: { organizationId: orgId },
  });
}

export async function fetchAllReposABIs(
  orgName: string,
  repoName: string,
  branch: string,
  orgId: string
) {
  const name = makeAbiIdentifier(orgName, repoName, branch);
  return await prisma.aBIData.findMany({
    where: { identifier: name, organizationId: orgId },
  });
}

// To Return one ABI if available
// NOTE: This doesn't check if the caller is allowed to perform the call
// NOTE: USED TO SKIP JOBS
export async function riskyFetchAllReposABIs(
  orgName: string,
  repoName: string,
  branch: string
) {
  const name = makeAbiIdentifier(orgName, repoName, branch);
  return await prisma.aBIData.findMany({
    where: { identifier: name },
    orderBy: {
      createdAt: "desc", // Get latest
    },
  });
}

export async function fetchLatestRepoABI(
  orgName: string,
  repoName: string,
  branch: string
) {
  const name = makeAbiIdentifier(orgName, repoName, branch);
  return await prisma.aBIData.findFirst({
    where: { identifier: name },
    orderBy: {
      createdAt: "desc", // Latest by definition
    },
  });
}
