import express from "express";
import { Request, Response } from "express";
import { requireSuperAdmin } from "../../../middleware/auth";
import { getCounts } from "../../../db/stats";

const router = express.Router();
export default router;

router.get("/public-digest", async (req: Request, res: Response) => {
  const data = await getCounts();

  const returnableData = {
    abiJobCount: data.abiJobCount,
    abiDataCount: data.abiDataCount,
    userCount: data.userCount,
  };

  // NOTE: You cannot delete the org because it will have jobs
  // Deleting org is more complex
  return res.json({
    message: "Here you go with main stats",
    data: returnableData,
  });
});

router.get(
  "/digest",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    // Get User, Orgs and Abi Jobs

    const data = await getCounts();

    // NOTE: You cannot delete the org because it will have jobs
    // Deleting org is more complex
    return res.json({
      message: "Here you go with main stats",
      data,
    });
  }
);
