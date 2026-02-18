import { Request, Response } from "express";
import express from "express";
import { requireSuperAdmin } from "../../middleware/auth";
import {
  createMagicInviteCode,
  createMagicInviteCodeCustom,
  deleteMagicInviteCode,
  listMagicInviteCodes,
} from "../../db/magicInviteCodes";
import { grantOrgMagicCredit, getOrgMagicCredits } from "../../db/magicCredits";

const router = express.Router();
export default router;

// Create a new magic invite code (auto-generated UUID)
router.post("/codes", requireSuperAdmin, async (req: Request, res: Response) => {
  try {
    const adminId = req.user?.userData?.id || "dev-admin";
    const code = await createMagicInviteCode(adminId);

    return res.json({
      message: "Magic invite code created",
      data: code,
    });
  } catch (error) {
    console.error("Error creating magic invite code:", error);
    return res.status(500).json({ error: "Failed to create code" });
  }
});

// Create a new magic invite code with custom memorable string
router.post(
  "/codes/custom",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    try {
      const { code } = req.body;

      if (!code || typeof code !== "string") {
        return res.status(400).json({ error: "Code is required" });
      }

      if (code.length < 4) {
        return res
          .status(400)
          .json({ error: "Code must be at least 4 characters" });
      }

      const adminId = req.user?.userData?.id || "dev-admin";
      const inviteCode = await createMagicInviteCodeCustom(code.trim(), adminId);

      return res.json({
        message: "Custom magic invite code created",
        data: inviteCode,
      });
    } catch (error: any) {
      console.error("Error creating custom magic invite code:", error);

      // Handle unique constraint violation
      if (error.code === "P2002") {
        return res.status(400).json({ error: "Code already exists" });
      }

      return res.status(500).json({ error: "Failed to create code" });
    }
  }
);

// List all magic invite codes
router.get("/codes", requireSuperAdmin, async (req: Request, res: Response) => {
  try {
    const codes = await listMagicInviteCodes();

    return res.json({
      message: "All magic invite codes",
      data: codes,
    });
  } catch (error) {
    console.error("Error listing magic invite codes:", error);
    return res.status(500).json({ error: "Failed to list codes" });
  }
});

// Delete an unused magic invite code
router.delete(
  "/codes/:code",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    try {
      const { code } = req.params;

      await deleteMagicInviteCode(code);

      return res.json({
        message: "Magic invite code deleted",
      });
    } catch (error: any) {
      console.error("Error deleting magic invite code:", error);

      if (error.message === "Code not found") {
        return res.status(404).json({ error: "Code not found" });
      }

      if (error.message === "Cannot delete a redeemed code") {
        return res.status(400).json({ error: "Cannot delete a redeemed code" });
      }

      return res.status(500).json({ error: "Failed to delete code" });
    }
  }
);

// Grant +1 magic credit to an organization
router.post(
  "/grant/:orgId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    try {
      const { orgId } = req.params;

      const newBalance = await grantOrgMagicCredit(orgId);

      return res.json({
        message: "Magic credit granted",
        data: {
          orgId,
          newBalance,
        },
      });
    } catch (error: any) {
      console.error("Error granting magic credit:", error);

      if (error.code === "P2025") {
        return res.status(404).json({ error: "Organization not found" });
      }

      return res.status(500).json({ error: "Failed to grant credit" });
    }
  }
);

// Get an organization's magic credit balance (for support)
router.get(
  "/org/:orgId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    try {
      const { orgId } = req.params;

      const credits = await getOrgMagicCredits(orgId);

      return res.json({
        message: "Organization magic credits",
        data: {
          orgId,
          credits,
        },
      });
    } catch (error) {
      console.error("Error getting org magic credits:", error);
      return res.status(500).json({ error: "Failed to get credits" });
    }
  }
);
