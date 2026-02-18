import { Request, Response } from "express";
import express from "express";

import { requireSuperAdmin } from "../../middleware/auth";
import {
  unsafeCreateCampaign,
  unsafeDeleteCampaign,
  unsafeFetchAllCampaigns,
} from "../../db/campaigns";

const router = express.Router();
export default router;

// Get all Campaigns in the system
router.get("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const foundCampaigns = await unsafeFetchAllCampaigns();

  return res.json({
    message: "All Campaigns",
    data: foundCampaigns,
  });
});

router.post("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const createdCampaign = await unsafeCreateCampaign(req.body);

  return res.json({
    message: "Created Campaign",
    data: createdCampaign,
  });
});

router.delete(
  "/:campaignId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { campaignId } = req.params;

    const deletedCampaign = await unsafeDeleteCampaign(campaignId);

    return res.json({
      message: "Delete Campaign",
      data: deletedCampaign,
    });
  }
);
