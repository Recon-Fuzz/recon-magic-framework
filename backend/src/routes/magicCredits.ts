import { Request, Response } from "express";
import express from "express";
import { BILLING_STATUS } from "@prisma/client";
import { onlyLoggedIn } from "../middleware/auth";
import { getOrgMagicCredits, hasOrgRedeemedCode } from "../db/magicCredits";
import { redeemMagicInviteCode } from "../db/magicInviteCodes";
import { getOrganization } from "../db/organizations";

const router = express.Router();
export default router;

// Get org's magic credit balance and status
router.get("/balance", onlyLoggedIn, async (req: Request, res: Response) => {
  try {
    const orgId = req.user.userData!.organizationId;
    const org = await getOrganization(orgId);

    if (!org) {
      return res.status(404).json({ error: "Organization not found" });
    }

    const isPro =
      org.billingStatus === BILLING_STATUS.PAID ||
      org.billingStatus === BILLING_STATUS.TRIAL;
    const credits = org.magicCredits;
    const hasRedeemedCode = await hasOrgRedeemedCode(orgId);

    return res.json({
      credits,
      isPro,
      canUseMagic: isPro || credits > 0,
      hasRedeemedCode,
    });
  } catch (error) {
    console.error("Error getting magic credits balance:", error);
    return res.status(500).json({ error: "Failed to get credit balance" });
  }
});

// Redeem an invite code
router.post("/redeem", onlyLoggedIn, async (req: Request, res: Response) => {
  try {
    const { code } = req.body;

    if (!code || typeof code !== "string") {
      return res.status(400).json({ error: "Code is required" });
    }

    const orgId = req.user.userData!.organizationId;

    const result = await redeemMagicInviteCode(code.trim(), orgId);

    return res.json({
      success: true,
      credits: result.org.magicCredits,
      message: "Code redeemed successfully",
    });
  } catch (error: any) {
    console.error("Error redeeming magic invite code:", error);

    // Return user-friendly error messages
    if (error.message === "Organization has already redeemed an invite code") {
      return res.status(400).json({
        success: false,
        error: "ALREADY_REDEEMED",
        message: "Your organization has already redeemed an invite code",
      });
    }

    if (error.message === "Invalid invite code") {
      return res.status(400).json({
        success: false,
        error: "INVALID_CODE",
        message: "Invalid invite code",
      });
    }

    if (error.message === "Code has already been redeemed") {
      return res.status(400).json({
        success: false,
        error: "CODE_USED",
        message: "This code has already been used",
      });
    }

    return res.status(500).json({
      success: false,
      error: "UNKNOWN",
      message: "Failed to redeem code",
    });
  }
});
