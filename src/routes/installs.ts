import { Request, Response } from "express";
import express from "express";
import { onlyLoggedIn } from "../middleware/auth";
import { getUserInstalledRepos, optimizedGetUserInstalledRepos } from "../github/installations";

const router = express.Router();
export default router;

// GET /installs
// NOTE: Slow AF but always up to date since it relies on GH
router.get("/slow", onlyLoggedIn, async (req: Request, res: Response) => {
  // Given logged in user
  // Let's grab the installs for the app
  // So we know which repos have been installed

  // TODO: We need to be logged in and from being logged in we use their token

  const projects = await getUserInstalledRepos(req.user.id);

  res.json({ message: "All your installs", data: projects });
});


router.get("/", onlyLoggedIn, async (req: Request, res: Response) => {
  // NOTE: Could skip the only loggedin, if you audit this, then remove it after audit
  if(!req.headers.authorization) {
    res.status(401);
    return res.json({ message: "Unauthorized" });
  }
  
  const projects = await optimizedGetUserInstalledRepos(req.headers.authorization);
  res.json({ message: "All your installs", data: projects });
});