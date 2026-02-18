import { Request, Response } from "express";
import express from "express";
import { onlyLoggedIn } from "../middleware/auth";
import {
  createUserAndFreeOrg,
  createUserFromOrgInvite,
  userUseInviteAndJoinId,
} from "../db/users";
import { getOrganization } from "../db/organizations";
import { sanitizeInput } from "../middleware/sanitizer";

const router = express.Router();
export default router;

/** Allow Anyone to Create an Org or Join */
// NOTE: If you create it this way it means you don't have an invite
router.post("/", onlyLoggedIn, sanitizeInput, async (req: Request, res: Response) => {
  // Check if user already has an org
  if (req.user.userData?.organizationId) {
    res.status(500);
    return res.json({
      message: "You already have an Organization, contract staff",
    });
  }

  let newUser;
  const { inviteCode } = req.body;

  if (inviteCode) {
    newUser = await createUserFromOrgInvite(inviteCode, String(req.user.id));
  } else {
    // This ensures that any user has a org by default
    newUser = await createUserAndFreeOrg(String(req.user.id), req.user.login);
  }

  return res.json({
    message: "Create a new user!",
    data: newUser,
  });
});

router.post("/join", onlyLoggedIn, sanitizeInput, async (req: Request, res: Response) => {
  // Consume invite
  // Update user to Org
  const { inviteCode } = req.body;

  // NOTE: By definition will throw if invite is invalid
  // or missing

  const updatedUser = await userUseInviteAndJoinId(
    inviteCode,
    String(req.user.id)
  );

  return updatedUser; // TODO: FIX RETURN DATA
});

router.get("/my", onlyLoggedIn, async (req: Request, res: Response) => {
  // Check if user already has an org
  if (req.user.userData?.organizationId) {
    const orgData = await getOrganization(req.user.userData.organizationId);
    return res.json({
      message: "Data for your organization",
      data: orgData,
    });
  }

  res.status(404);
  return res.json({
    message: "You don't belong to any organization!",
    data: {},
  });
});

// TODO Event "has receive premium"
// To toggle an extra page on Recon App to explain stuff
