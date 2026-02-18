import { Request, Response } from "express";
import express from "express";
import { findChatIdByUsername, sendMessage } from "../utils/telegram";
import { onlyLoggedIn, orgCheck, requireProOrg } from "../middleware/auth";

const router = express.Router();
export default router;

const EXAMPLE_BROKEN_PROPERTY = `
NOTE: THIS IS A TEST MESSAGE!
BROKEN PROPERTIES WILL LOOK AS FOLLOWS:

⚠️⚠️⚠️ 
 Broken Property: property_user_offset_is_always_greater_than_start 
 Job link: https://getrecon.xyz/dashboard/jobs/job_id
`

router.post(
  "/testChat",
  onlyLoggedIn,
  orgCheck,
  requireProOrg,
  async (req: Request, res: Response) => {
    const { username } = req.body;
    try {
      const chatId = await findChatIdByUsername(username);
      if(!chatId) {
        return res.status(404).json({ message: "Chat not found" });
      }
      await sendMessage(EXAMPLE_BROKEN_PROPERTY, chatId);
      res.status(200).json({ message: "chatId found", data: chatId });
    } catch (err) {
      res.status(500).json({ message: "Error retrieving the chat id" });
    }
  }
);

router.post(
  "/sendMessage",
  onlyLoggedIn,
  orgCheck,
  requireProOrg,
  async (req: Request, res: Response) => {
    const { chatId, text } = req.body;
    try {
      await sendMessage(text, chatId);
      res.status(200).json({ message: "Message sent" });
    } catch (err) {
      res.status(500).json({ message: "Error sending message" });
    }
  }
);
