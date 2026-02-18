import { Request, Response } from "express";

import express from "express";
import { onlyLoggedIn, orgCheck } from "../middleware/auth";
import { sanitizeInput } from "../middleware/sanitizer";
import { createApiKey, deleteApiKey, fetchApiKeysByUserId } from "../db/apiKey";

const router = express.Router();
export default router;


router.post("/", onlyLoggedIn, orgCheck, sanitizeInput, async (req: Request, res: Response) => {
  const { canWrite, label } = req.body;
  const apiKey = await createApiKey(req.user.userData!.id, canWrite, label);
  res.json({ message: "API Key created", data: apiKey });
});

router.get("/", onlyLoggedIn, orgCheck, async (req: Request, res: Response) => {
  const apiKeys = await fetchApiKeysByUserId(req.user.userData!.id);
  res.json({ message: "API Keys fetched", data: apiKeys });
});

router.delete("/", onlyLoggedIn, orgCheck, async (req: Request, res: Response) => {
  const { apiKeyId } = req.body;
  const apiKey = await deleteApiKey(apiKeyId, req.user.userData!.id);
  res.json({ message: "API Key deleted", data: apiKey });
});