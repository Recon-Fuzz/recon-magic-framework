import { Request, Response } from "express";

import express from "express";
import { onlyLoggedIn } from "../middleware/auth";

const router = express.Router();
export default router;

// Uses LoggedIn Middleware to Fetch User Data and return the email
// NOTE We remove email and instead use user ID cause it's better for relations and faster loading
// NOTE: That's cause email is not guaranteed to exist, whereas id is
// And we need id to find user token, find user repos, etc...

// GET /auth/me
router.get("/me", onlyLoggedIn, async (req: Request, res: Response) => {
  // We can get the ID and the Login from there
  return res.json({
    message: `Logged in as ${req?.user?.id}`,
    data: req?.user?.id,
  });
});
