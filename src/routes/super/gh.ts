import express from "express";
import { Request, Response } from "express";

import axios from "axios";
import { githubAppClientID, githubAppSecret } from "../../config/config";
import { isUserIdCollaborator } from "../../github/installations";

const router = express.Router();
export default router;

// Extra route to expire a GH token, used for safety
export async function expireGhToken(tokenString: string) {
  const token = tokenString.split("Bearer ")[1]; // Get part after

  const res = await axios({
    method: "DELETE",
    url: `https://api.github.com/applications/${githubAppClientID}/token`,
    auth: {
      username: githubAppClientID,
      password: githubAppSecret,
    },
    data: {
      access_token: token,
    },
  });

  if (res.status !== 204) {
    throw new Error(`Failed to expire the token ${token}`);
  }
}

router.get("/isCollaborator", async (req: Request, res: Response) => {
  const { owner, repo, userId } = req.body;
  const isCollaborator = await isUserIdCollaborator(owner, repo, userId);
  return res.json({ message: "isCollaborator", data: isCollaborator });
});

router.post("/expire", async (req: Request, res: Response) => {
  const bearer = req.headers.authorization;
  if (!bearer) {
    res.status(401);
    return res.json({ message: "Unauthorized" });
  }

  try {
    await expireGhToken(bearer);
  } catch (e) {
    return res.json({ message: "Probably already expired", data: {} });
  }

  return res.json({ message: "expired", data: {} });
});
