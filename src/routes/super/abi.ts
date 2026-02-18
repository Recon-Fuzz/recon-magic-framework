import express from "express";
import { Request, Response } from "express";
import {
  createNewAbiData,
  fetchAllOrgAbiData,
  fetchAllSystemAbiData,
  superDeleteAbiData,
  updateAbiData,
} from "../../db/abis";
import { requireSuperAdmin } from "../../middleware/auth";

const router = express.Router();
export default router;

/**
 * /super/abi/
 */

/** ABI */
// Fetches all the ABI data from the db
router.get("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const allAbiData = await fetchAllSystemAbiData();

  return res.json({
    message: "All system abi data",
    data: allAbiData,
  });
});

// Allows superAdmin to manually add ABI data for a specified org and repo
router.post("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const { orgId, orgName, repoName, branch, commit, abiData } = req.body;

  // NOTE: SANITIZATION AND VALIDATION

  const result = await createNewAbiData(
    orgName,
    repoName,
    branch,
    commit,
    abiData,
    orgId
  );

  return res.json({
    message: "Manually added ABI Data to the org",
    data: result,
  });
});

router.get(
  "/:orgId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { orgId } = req.params;

    const allAbiData = await fetchAllOrgAbiData(orgId);

    return res.json({
      message: `All Org with id: ${orgId}, abiData`,
      data: allAbiData,
    });
  }
);

router.put(
  "/:abiId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { abiId } = req.params;
    const { commit, abiData } = req.body; // TODO TEST

    const result = await updateAbiData(abiId, commit, abiData);

    return res.json({ message: `Updated ${abiId}`, data: result });
  }
);

router.delete(
  "/:abiId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { abiId } = req.params;

    const result = await superDeleteAbiData(abiId);

    return res.json({ message: `Deleted ${abiId}`, data: result });
  }
);
