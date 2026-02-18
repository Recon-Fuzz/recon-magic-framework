import { telegramBotToken } from "../config/config";

/*
1. Send message
2. Get chatId from username


Flow:
1. ON  FE, user must add their username
2. user should start a conversation with the bot
3. Api call to findChatId
3.1. If chatId is not found, send message to user to start a conversation with the bot
3.2. If chatId is found, send message to user && store chatId in DB
4. User can now receive messages from the bot
*/
const TELEGRAM_API_URL = `https://api.telegram.org/bot${telegramBotToken}/sendMessage`;
const TELEGRAM_API_URL_GET_CHATS = `https://api.telegram.org/bot${telegramBotToken}/getUpdates`;

export async function sendMessage(text: string, chatId: number) {
  try {
    const response = await fetch(TELEGRAM_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text,
      }),
    });

    const data = await response.json();
    console.log("Message sent:", data);
  } catch (error) {
    console.error("Error sending message:", error);
  }
}

export async function findChatIdByUsername(username: string): Promise<number | null> {
  try {
    const response = await fetch(TELEGRAM_API_URL_GET_CHATS);
    const data = await response.json() as UpdateRes;

    if (!data.ok) {
      console.error("Error fetching updates:", data);
      return null;
    }

    // Look through updates for the username
    for (const update of data.result) {
      const chat = update.message?.chat || update.channel_post?.chat;
      if (chat && chat.username === username) {
        return chat.id;
      }
    }

    throw new Error(`No chat found for username: ${username}`);
  } catch (error) {
    console.error("Error finding chat ID:", error);
    throw new Error("Couldn't find chatId");
  }
}

interface UpdateRes {
  ok: boolean;
  result: any[];
}

// ?? Maybe not necessary
export async function getChats() {
  try {
    const response = await fetch(TELEGRAM_API_URL_GET_CHATS);
    const data = await response.json() as UpdateRes;
    console.log(data)
    if (!data.ok) {
      console.error("Error fetching updates:", data);
      return;
    }

    // Extract unique chat IDs
    const chats = new Map<number, { id: number; type: string; title?: string }>();
    data.result.forEach((update: any) => {
      console.log(update)
      const chat = update.message?.chat || update.channel_post?.chat;
      if (chat) {
        chats.set(chat.id, { id: chat.id, type: chat.type, title: chat.title });
      }
    });

    console.log("Active Chats:", Array.from(chats.values()));
  } catch (error) {
    console.error("Error:", error);
  }
}
