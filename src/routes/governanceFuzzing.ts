import { Request, Response } from "express";
import express from "express";
import {
  onlyListenerFactory,
  onlyLoggedIn,
  orgCheck,
  requireProOrg,
} from "../middleware/auth";
import {
  createRecipe,
  getRecipeById,
  updateRecipeDisplayName,
} from "../db/recipes";
import {
  createGovFuzzing,
  deleteGovFuzzing,
  toggleGovFuzzing,
  getGovFuzzingByOrganizationId,
  createWsListener,
  addListenerToGovFuzzing,
  getLastCheckedBlock,
  updateBlockNumber,
  getAllActiveGovFuzzing,
  updateSubscriptionId,
  getGovFuzzingByRecipeId,
  updateGovFuzzing,
} from "../db/govFuzzing";
import { createHash } from "crypto";
import { createJob } from "../db/jobs";
import { sanitizePreprocess } from "../sanitizePreprocess";
import { getMetaData } from "../utils/metadata";

const router = express.Router();
export default router;

// Get
// PUT

//TODO ADD AUTH
router.get(
  "/recipes/:recipeId",
  onlyListenerFactory,
  async (req: Request, res: Response) => {
    const { recipeId } = req.params;
    try {
      const recipe = await getRecipeById(recipeId);
      res.status(200).json({ message: "Recipe found", data: recipe });
    } catch (err) {
      res.status(500).json({ message: "Error retrieving the recipe" });
    }
  }
);

router.post(
  "/",
  onlyLoggedIn,
  orgCheck,
  requireProOrg,
  async (req: Request, res: Response) => {
    // Add event definition
    const {
      contractAddress,
      topic,
      prepContract,
      recipeId,
      eventDefinition,
      chainId,
    } = req.body;

    try {
      const existingRecipe = await getRecipeById(recipeId);
      if (!existingRecipe) {
        return res.status(404).json({ message: "Recipe not found" });
      }

      const newRecipe = await createRecipe(
        existingRecipe,
        prepContract,
        chainId
      );
      const orgId = req.user.userData!.organizationId;
      const govFuzzing = await createGovFuzzing(
        newRecipe,
        contractAddress,
        topic,
        chainId,
        eventDefinition,
        orgId
      );

      await updateRecipeDisplayName(
        newRecipe.id,
        `Gov Fuzzing recipe for ${govFuzzing.id}`
      );
      const wsListener = await createWsListener(
        contractAddress,
        topic,
        chainId,
        eventDefinition,
        newRecipe.id,
        govFuzzing.id
      );
      await addListenerToGovFuzzing(
        govFuzzing.id,
        wsListener.data.subscriptionId
      );

      res.status(200).json({ message: "chatId found", data: "chatId" });
    } catch (err) {
      res.status(500).json({ message: "Error retrieving the chat id" });
    }
  }
);

router.get("/", onlyLoggedIn, orgCheck, async (req: Request, res: Response) => {
  const orgId = req.user.userData!.organizationId;
  try {
    const recipe = await getGovFuzzingByOrganizationId(orgId);
    res.status(200).json({ message: "Governance Fuzzing found", data: recipe });
  } catch (err) {
    res.status(500).json({ message: "Error retrieving the recipe" });
  }
});

router.delete(
  "/:id",
  onlyLoggedIn,
  orgCheck,
  async (req: Request, res: Response) => {
    const { id } = req.params;
    try {
      const recipe = await deleteGovFuzzing(id);
      res
        .status(200)
        .json({ message: "Governance Fuzzing deleted", data: recipe });
    } catch (err) {
      res.status(500).json({ message: "Error deleting the recipe" });
    }
  }
);

router.put(
  "/toggle/:id",
  onlyLoggedIn,
  orgCheck,
  async (req: Request, res: Response) => {
    const { id } = req.params;
    try {
      const govFuzzingObj = await toggleGovFuzzing(id);
      res
        .status(200)
        .json({ message: "Governance Fuzzing disabled", data: govFuzzingObj });
    } catch (err) {
      res.status(500).json({ message: "Error disabling the govFuzzingObj" });
    }
  }
);

router.put(
  "/",
  onlyLoggedIn,
  orgCheck,
  requireProOrg,
  async (req: Request, res: Response) => {
    const { id, chainId, address, eventDefinition, topic, prepareContracts } =
      req.body;

    try {
      const govFuzzingObj = await updateGovFuzzing(
        id,
        parseInt(chainId),
        address,
        eventDefinition,
        topic,
        prepareContracts
      );
      res
        .status(200)
        .json({ message: "Governance Fuzzing disabled", data: govFuzzingObj });
    } catch (err) {
      console.log(err);
      res.status(500).json({ message: "Error updating the govFuzzingObj" });
    }
  }
);

// POST - create new block
// GET - Get last checked block number ( chaind ID )

// Add middleware to only access from factory listener
router.put(
  "/block/:id",
  onlyListenerFactory,
  async (req: Request, res: Response) => {
    const { id } = req.params;
    const { blockNumber } = req.body;
    try {
      const block = await updateBlockNumber(id, blockNumber);
      res.status(200).json({ message: "Block number updated", data: block });
    } catch (err) {
      res.status(500).json({ message: "Error updating the block number" });
    }
  }
);

router.get(
  "/block/:id",
  onlyListenerFactory,
  async (req: Request, res: Response) => {
    const { id } = req.params;
    try {
      const block = await getLastCheckedBlock(id);
      res.status(200).json({ message: "Block number found", data: block });
    } catch (err) {
      res.status(500).json({ message: "Error retrieving the block number" });
    }
  }
);

// TODO: ???
router.post(
  "/jobs",
  onlyListenerFactory,
  async (req: Request, res: Response) => {
    // Get params from Body
    const {
      id,
      organizationId,
      orgName,
      repoName,
      ref,
      directory,
      duration,
      preprocess,
      fuzzerArgs,
      fuzzer,
      label,
    } = req.body;

    //TODO 0XSI
    // After Corn engagement, remove this line
    const isCorn =
      (orgName.toLowerCase() === "usecorn") || (organizationId == "7e658035-9e30-4495-9fbe-f6277888afe1");
    const isAllowedScripts = isCorn;
    let otherScript = undefined;
    if (isCorn && repoName === "bitcorn-oft") {
      otherScript = `yarn install`
    } else if (isCorn && repoName === "airdrop-contracts") { 
      otherScript = `echo "y" && pnpm install`;
    }

    let suppliedMetadata: any = {
      startedBy: createHash("sha256")
        .update(organizationId.toString())
        .digest("hex"),
      method: "factory-listener",
    };
    let metadata;
    // Fetch the token
    try {
      metadata = await getMetaData(suppliedMetadata, orgName, repoName, ref);
    } catch {
      console.log("Job: couldn't create access token");
    }

    // const govFuzzing = await getGovFuzzingByRecipeId(id);

    const job = await createJob(
      organizationId,
      orgName,
      repoName,
      ref,
      fuzzer,
      label,
      {
        fuzzerArgs,
        directory,
        duration,
        preprocess: sanitizePreprocess(
          preprocess,
          isAllowedScripts,
          otherScript
        ),
        metadata: metadata ? metadata : suppliedMetadata, // there will always be metadata in this case
      },
      id // Recipe ID
    );

    return res.json({ message: `Created a Job for your org`, data: job });
  }
);

router.get(
  "/allActive",
  onlyListenerFactory,
  async (req: Request, res: Response) => {
    const jobs = await getAllActiveGovFuzzing();
    res.status(200).json({ message: "Jobs found", data: jobs });
  }
);

router.put(
  "/subscriptionId/:id",
  onlyListenerFactory,
  async (req: Request, res: Response) => {
    const { id } = req.params;
    const { wsListenerId } = req.body;
    const govFuzzing = await updateSubscriptionId(id, wsListenerId);
    res
      .status(200)
      .json({ message: "Subscription ID updated", data: govFuzzing });
  }
);
