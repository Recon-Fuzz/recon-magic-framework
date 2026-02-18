import { Recipe } from "@prisma/client";
import prisma from "./client";
import axios from "axios";
import {
  factoryListenerAddress,
  factoryListenerSecret,
} from "../config/config";

export async function createGovFuzzing(
  recipe: Recipe,
  address: string,
  topic: string,
  chainId: number,
  eventDefinition: string,
  organizationId: string
) {
  return await prisma.governanceFuzzing.create({
    data: {
      recipeId: recipe.id,
      address,
      topic,
      chainId,
      eventDefinition,
      organizationId,
      recipes: { connect: { id: recipe.id } },
      lastCheckedBlock: 0,
      lastCheckedAt: new Date(),
    },
  });
}

export async function getGovFuzzingById(id: string) {
  return await prisma.governanceFuzzing.findUnique({
    where: { id },
  });
}

export async function getGovFuzzingByRecipeId(recipeId: string) {
  return await prisma.governanceFuzzing.findMany({
    where: { recipeId },
  });
}

export async function getGovFuzzingByOrganizationId(organizationId: string) {
  return await prisma.governanceFuzzing.findMany({
    where: { organizationId },
    include: { recipes: {
      include: {
        jobs: true
      }
    } },
  });
}

export async function getAllGovernanceFuzzing() {
  return await prisma.governanceFuzzing.findMany();
}

export async function deleteGovFuzzing(id: string) {
  // Create a batch to delete both the governance fuzzing and the recipe
  const governanceFuzzing = await prisma.governanceFuzzing.findUnique({
    where: { id },
  });
  if (!governanceFuzzing) {
    throw new Error("Governance Fuzzing not found");
  }

  // Disable the ws listener
  try {
    await axios({
      method: "POST",
      url: `${factoryListenerAddress}/unsubscribe`,
      data: {
      subscriptionId: governanceFuzzing.wsListenerId,
      chain: governanceFuzzing.chainId,
    },
    headers: {
        Authorization: `Bearer ${factoryListenerSecret}`,
      },
    });
  } catch (error) {
    // We continue execution as the listener will be disabled on cycling anyway
    console.error("Error disabling ws listener", error);
  }

  return await prisma.$transaction([
    prisma.governanceFuzzing.delete({
      where: { id },
    }),
    prisma.recipe.delete({
      where: { id: governanceFuzzing.recipeId },
    }),
  ]);
}

export async function toggleGovFuzzing(id: string) {
  const govFuzzing = await prisma.governanceFuzzing.findUnique({
    where: { id },
  });
  if (!govFuzzing) {
    throw new Error("Governance Fuzzing not found");
  }
  try {
    if (govFuzzing.enabled) {
      const wsListener = await axios({
        method: "POST",
        url: `${factoryListenerAddress}/unsubscribe`,
        data: {
        subscriptionId: govFuzzing.wsListenerId,
        chain: govFuzzing.chainId,
      },
      headers: {
          Authorization: `Bearer ${factoryListenerSecret}`,
        },
      });
      if (wsListener.status === 200) {
        console.log("Unsubscribed from factory listener", wsListener.data);
        return await prisma.governanceFuzzing.update({
          where: { id },
          data: { enabled: false, wsListenerActive: false },
        });
      }
    } else {
      const wsListener = await axios({
        method: "POST",
        url: `${factoryListenerAddress}/resubscribe`,
        data: {
          address: govFuzzing.address,
          topic: govFuzzing.topic,
          chain: govFuzzing.chainId,
          eventDefinition: govFuzzing.eventDefinition,
          recipeId: govFuzzing.recipeId,
          govFuzzingId: govFuzzing.id,
        },
        headers: {
          Authorization: `Bearer ${factoryListenerSecret}`,
        },
      });

      if (wsListener.status === 200) {
        return await prisma.governanceFuzzing.update({
          where: { id },
          data: { enabled: true, wsListenerActive: true, wsListenerId: wsListener.data.data.subscriptionId },
        });
      }
    }
  } catch (error) {
    console.error("Error unsubscribing from factory listener", error);
    throw error;
  }
  return 
}

export async function createWsListener(
  address: string,
  topic: string,
  chainId: number,
  eventDefinition: string,
  recipeId: string,
  govFuzzingId: string
) {
  console.log("Start to create ws listener", govFuzzingId);
  try {
    const wsListener = await axios({
      method: "POST",
      url: `${factoryListenerAddress}/subscribe`,
      data: {
        address,
        topic,
        chain: chainId,
        eventDefinition,
        recipeId,
        govFuzzingId,
      },
      headers: {
        Authorization: `Bearer ${factoryListenerSecret}`,
      },
    });
    console.log("Ws listener created", wsListener.data);
    return wsListener.data;
  } catch (error) {
    console.error("Error creating ws listener", error);
    throw error;
  }
}

export async function addListenerToGovFuzzing(
  id: string,
  wsListenerId: string
) {
  return await prisma.governanceFuzzing.update({
    where: { id },
    data: { wsListenerId, wsListenerActive: true },
  });
}

export async function updateBlockNumber(id: string, blockNumber: number) {
  return await prisma.governanceFuzzing.update({
    where: { id },
    data: { lastCheckedBlock: blockNumber },
  });
}

export async function updateLastCheckedAt(id: string) {
  return await prisma.governanceFuzzing.update({
    where: { id },
    data: { lastCheckedAt: new Date() },
  });
}

export async function getLastCheckedBlock(id: string) {
  return await prisma.governanceFuzzing.findUnique({
    where: { id },
  });
}

export async function getAllActiveGovFuzzing() {
  return await prisma.governanceFuzzing.findMany({
    where: { enabled: true },
  });
}

export async function updateSubscriptionId(id: string, wsListenerId: string) {
  return await prisma.governanceFuzzing.update({
    where: { id },
    data: { wsListenerId },
  });
}

export async function updateGovFuzzing(id: string, chainId: number, address: string, eventDefinition: string, topic: string, prepareContracts: any) {
  const existingGovFuzzing = await prisma.governanceFuzzing.findUnique({
    where: { id },
  });

  if (!existingGovFuzzing) {
    throw new Error("Governance Fuzzing not found");
  }
  const associatedRecipe = await prisma.recipe.findUnique({
    where: {
      id: existingGovFuzzing.recipeId
    }
  });

  if (!associatedRecipe) {
    throw new Error("Recipe not found");
  }

  let forkMode = "TESTNET-SEPOLIA"; // TODO CHANGE THAT
  // Map to whatever the runner expects
  if (chainId) {
    switch (chainId) {
      case 1:
        forkMode = "MAINNET";
        break;
      case 11155111:
        forkMode = "TESTNET-SEPOLIA";
        break;
      case 5:
        forkMode = "TESTNET-GOERLI";
        break;
      case 137:
        forkMode = "POLYGON";
        break;
      case 42161:
        forkMode = "ARBITRUM";
        break;
      case 10:
        forkMode = "OPTIMISM";
        break;
      case 534352:
        forkMode = "SCROLL";
        break;
      case 21000001:
        forkMode = "TESTNET-CORN";
        break;
      case 21000000:
        forkMode = "MAINNET-CORN";
        break;
      default:
        forkMode = `TESTNET-${chainId}`;
        break;
    }
  }

  return await prisma.$transaction([
    prisma.recipe.update({
      where: { id: associatedRecipe.id },
      data: { 
        fuzzerArgs: {
          ...associatedRecipe.fuzzerArgs as any,
          prepareContracts,
          forkMode
        }
      }
    }),
    prisma.governanceFuzzing.update({
      where: { id },
      data: { chainId, address, eventDefinition, topic }
    })
  ]);
}