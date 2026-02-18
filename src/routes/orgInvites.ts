import { Request, Response } from "express";
import express from "express";
import { onlyLoggedIn, orgCheck, requireProOrg } from "../middleware/auth";
import { createInviteToOrg } from "../db/orgInvites";

const router = express.Router();
export default router;

// Create an invite for your org
// NOTE: The ID is ONE TIME USE
// DO NOT SHARE THE ID
router.post(
  "/",
  onlyLoggedIn,
  requireProOrg,
  orgCheck,
  async (req: Request, res: Response) => {
    // Create a new invite
    const invite = await createInviteToOrg(req.user.userData!.organizationId);
    return res.json({
      message: `Created Invite with code ${invite.id}`,
      data: invite,
    });

    // Give a code to a user to invite them
    // TODO: Could also check for EMAIL / GITHUB ID
    // That would be even more resilient
  }
);
