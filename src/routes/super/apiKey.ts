import { Request, Response } from "express";

import express from "express";
import { createApiKey, deleteApiKey, fetchApiKeysByUserId, unsafeDeleteApiKey } from "../../db/apiKey";
import { requireSuperAdmin } from "../../middleware/auth";

const router = express.Router();
export default router;


router.get("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const { userId } = req.params;
  const apiKeys = await fetchApiKeysByUserId(userId);
  res.json({ message: "API Keys fetched", data: apiKeys });
});

router.delete("/:id", requireSuperAdmin, async (req: Request, res: Response) => {
  const { id } = req.params;
  const apiKey = await unsafeDeleteApiKey(id);
  res.json({ message: "API Key deleted", data: apiKey });
});