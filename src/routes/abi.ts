import { Request, Response } from "express";

import express from "express";
import { onlyLoggedIn, orgCheck } from "../middleware/auth";
import { deleteAbiData, fetchAllOrgAbiData, fetchAllReposABIs } from "../db/abis";
import { sanitizeInput } from "../middleware/sanitizer";

const router = express.Router();
export default router;

router.get("/", onlyLoggedIn, orgCheck, async (req: Request, res: Response) => {
  try {
    const allAbiData = await fetchAllOrgAbiData(
      req.user.userData!.organizationId
    );
    return res.json({ message: "All your org abi data", data: allAbiData });
  } catch (error) {
    console.error("error getting the abi data:", error);
    res.status(500);
    return res.json({ message: "Error fetching all abi data", data: {} });
  }
});

router.delete("/:abiId", onlyLoggedIn, orgCheck, async (req: Request, res: Response) => {
  const { abiId } = req.params;
  const orgId = req.user.userData!.organizationId;


  try {
    const responseFromDelete = await deleteAbiData(abiId, orgId);
    res.status(200);
    return res.json({ message: "Deleted abi data", data: responseFromDelete });
  } catch (error) {
    console.error("error deleting the abi data:", error);
    res.status(500);
    return res.json({ message: "Error deleting abi data", data: {} });
  }
});

router.get(
  "/:orgName/:repoName/:branch",
  onlyLoggedIn,
  orgCheck,
  sanitizeInput,
  async (req: Request, res: Response) => {
    // TODO: Check if user has permission for that repoABI
    // Specifically, we need to fetch the Repo Abi for the org
    // Fetching any repo Abi should not be allowed

    const { orgName, repoName, branch } = req.params;
    const allResults = await fetchAllReposABIs(
      orgName,
      repoName,
      branch,
      req.user.userData!.organizationId
    );

    const parsed = allResults.map((result) => ({
      ...result,
      abiData: JSON.parse(result.abiData as string), // NOTE: TODO: Type mess
    }));

    if (parsed.length === 0) {
      res.status(404);
      return res.json({ message: "No Repo ABI found for a specific repo", data: {} });
    }

    // NOTE: Given one commit we should always only get one
    // This is broken locally
    // And should be enforced
    // NOTE: Will return empty list, we may want to have a 404
    res.json({ message: "Repo ABI for the specific repo", data: parsed });
  }
);
