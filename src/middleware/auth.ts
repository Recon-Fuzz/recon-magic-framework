// Middleware for Authentication
import { Request, Response, NextFunction } from "express";
import { getUserInfo } from "../db/users";
import { getOrganization } from "../db/organizations";
import { BILLING_STATUS } from "@prisma/client";
import axios from "axios";
import {
  claudeSecret,
  factoryListenerSecret,
  githubAppClientID,
  githubAppSecret,
  jsonWebTokenSecretRunner,
  nodeEnv,
  unsafeSkipAdminCheck,
} from "../config/config";
import { fetchListener } from "../db/listener";
import jwt from "jsonwebtoken";
import { fetchApiKeyById } from "../db/apiKey";

async function verifyApiKey(id: string) {
  const apiKeyId = id.split("Bearer ")[1]; // Get part after

  const apiKey = await fetchApiKeyById(apiKeyId);
  if(!apiKey) {
    throw new Error("Invalid API Key");
  }
  return {
    id: apiKey.id,
    userId: apiKey.userId,
    canWrite: apiKey.canWrite,
    label: apiKey.label,
  };
}

// NOTE: THROWS on 401 and on wrong auth
async function verifyOauthBelongsToAppAndRetrieveUserIdAndLogin(
  tokenString: string
): Promise<{ login: string; id: number }> {
  const token = tokenString.split("Bearer ")[1]; // Get part after

  const res = await axios({
    method: "POST",
    url: `https://api.github.com/applications/${githubAppClientID}/token`,
    auth: {
      username: githubAppClientID,
      password: githubAppSecret,
    },
    data: {
      access_token: token,
    },
  });

  if (res.data.app.client_id !== githubAppClientID) {
    throw new Error("Wrong GITHUB_APP_CLIENT_ID");
  }

  return {
    login: res.data.user.login,
    id: res.data.user.id,
  };
}


  
// NOTE: In the future we can do a redis cache for bearer token and user data
// Once we have validated them
// NOTE: We could also store the data in DB, but I think it's not great
// NOTE: LASTLY We could use a memory pointer and store it locally in the server memory, probably the most based solution, that saves money

// TODO: This ensures that login is done with correct App Id
// We should sync this with the App id on the Client
// This should ensure loging always works as intended
async function getUserData(token: string): Promise<Request["user"]> {
  // Must be bearer
  if(!token.startsWith("Bearer ")) {
    throw new Error("Invalid token");
  }

  if(token.startsWith("Bearer api_")) {
    // It's an API Key
    const { userId, canWrite } = await verifyApiKey(token);
    if(!canWrite) {
      throw new Error("Invalid API Key"); // TODO: Currently any ApiKey is a write api key since we override auth middleware
      // And we don't have custom visibility for api keys
      // TODO: We need to update the routes to add the write or use GH token each.
    }
    return {
      login: "",
      id: Number(userId),
      token,
      userData: await getUserInfo(String(userId)), // NOTE: Could be null
      authenticatedBy: canWrite ? "apiKeyWrite" : "apiKeyRead" as const,
    };
  }

  if(token.startsWith("Bearer ghu_")) {
    // Verify auth
    const { login, id } = await verifyOauthBelongsToAppAndRetrieveUserIdAndLogin(
      token
    );
    
    // Return available data
    return {
      login: login,
      id: id,
      token,
      userData: await getUserInfo(String(id)), // NOTE: Could be null
      authenticatedBy: "github" as const,
    };
  }

  // TODO: Implement Listener case

  throw new Error("Unhandled Case"); // NOTE: Must throw on error! We should not reach this point!
}

export async function onlyRunner(
  req: Request,
  res: Response,
  next: NextFunction
) {
  const bearer = req.headers.authorization;
  if (!bearer) {
    res.status(401);
    return res.json({ message: "Unauthorized" });
  }
  const valid = jwt.verify(bearer, jsonWebTokenSecretRunner);
  if (!valid) {
    res.status(401);
    return res.json({ message: "Invalid token" });
  } else {
    next();
  }
}
// TODO: Update this to use API keys as well
export async function onlyLoggedIn(
  req: Request,
  res: Response,
  next: NextFunction
) {
  const bearer = req.headers.authorization;
  if (!bearer) {
    res.status(401);
    return res.json({ message: "Unauthorized" });
  }

  let user;
  try {
    user = await getUserData(bearer);
  } catch (e) {
    res.status(500);
    return res.json({ message: "Something went wrong" });
  }

  // Should never happen, but may as well
  if (!user) {
    res.status(500);
    return res.json({ message: "Something went wrong" });
  }

  // Add to user object
  req.user = user;
  next();
}

export async function requireSuperAdmin(
  req: Request,
  res: Response,
  next: NextFunction
) {
  // Check users if not in dev
  // https://api.github.com/users/GalloDaSballo
  // https://api.github.com/users/aviggiano

  if (unsafeSkipAdminCheck === "true" && nodeEnv === "development") {
    // Skip checks if in DEV and we have the flag
    console.warn("Skipping Super Admin checks");
  } else {
    const bearer = req.headers.authorization;
    if (!bearer) {
      res.status(401);
      return res.json({ message: "Unauthorized" });
    }
    try {
      req.user = await getUserData(bearer);
    } catch {
      res.status(500);
      return res.json({
        message: "Error When trying to authenticate as super admin",
      });
    }

    // We should store this in a table maybe
    if (
      req.user.id != 13383782 && // Alex
      req.user.id != 3029017 && // Aviggiano
      req.user.id != 94120714 && // Nicanor
      // req.user.id != 65844331 && // Lourens
      req.user.id != 59468684 && // 0xsi
      req.user.id != 117800451 // Knot
    ) {
      res.status(401);
      return res.json({ message: "You're not a super admin" });
    }
  }

  next();
}

export async function requireProOrg(
  req: Request,
  res: Response,
  next: NextFunction
) {
  if (!req.user.userData?.organizationId) {
    res.status(401);
    return res.json({ message: "No Organization, Please register" });
  }

  const orgData = await getOrganization(req.user.userData.organizationId);

  // NOTE: Because of the pointer above, we should always get the org
  if (!orgData) {
    res.status(401);
    return res.json({ message: "No Organization, requireProOrg" });
  }

  if (
    orgData.billingStatus !== BILLING_STATUS.PAID &&
    orgData.billingStatus !== BILLING_STATUS.TRIAL
  ) {
    res.status(401);
    return res.json({ message: "Paid Plan Expired, please contact support" });
  }
  // Plan is paid, send them
  // NOTE: Rest of code needs to check for credits
  next();
}

export async function onlyClaude(
  req: Request,
  res: Response,
  next: NextFunction
) {
  const bearer = req.headers.authorization;

  if(!claudeSecret) {
    res.status(401);
    return res.json({ message: "Unauthorized" });
  }

  if (!bearer) {
    res.status(401);
    return res.json({ message: "Unauthorized" });
  }

  if (bearer.split(" ")[1] !== claudeSecret) {
    res.status(401);
    return res.json({ message: "Unauthorized" });
  }

  next();
}

export async function orgCheck(
  req: Request,
  res: Response,
  next: NextFunction
) {
  if (!req.user.userData?.organizationId) {
    res.status(400);
    return res.json({
      message: "Your account doesn't belong to an ORG, please talk to staff",
      data: {},
    });
  }
  next();
}

export async function onlyListenerFactory(
  req: Request,
  res: Response,
  next: NextFunction
) {
  // Check for bearer token vs FACTORY_LISTENER_SECRET
  const bearer = req.headers.authorization;

  if(!factoryListenerSecret) {
    res.status(401);
    return res.json({ message: "Unauthorized" });
  }

  if (!bearer) {
    res.status(401);
    return res.json({ message: "Unauthorized" });
  }

  if (bearer.split(" ")[1] !== factoryListenerSecret) {
    res.status(401);
    return res.json({ message: "Unauthorized" });
  }

  next();
}

// This checks that the caller is a listener
export async function requireListener(
  req: Request,
  res: Response,
  next: NextFunction
) {

  let listenerOrg;

  // The bearer token will be the id of the listener
  const bearer = req.headers.authorization;
  if (!bearer) {
    res.status(401);
    return res.json({ message: "Unauthorized" });
  }

  // We clean the token
  const token = bearer?.replace("Bearer ", "");
  try {
    // We fetch the associated listener
    listenerOrg = await fetchListener(token);

    // For user related checks i.t.o job creation we populate the minimum required user data
    let user = {
      login: "",
      id: 0,
      token: "",
      authenticatedBy: "listener" as const,
      userData: {
        id: listenerOrg.id,
        organizationId: listenerOrg.organizationId,
        createdAt: listenerOrg.createdAt,
        updatedAt: listenerOrg.createdAt,
      },
    };

    req.user = user;
  } catch (e){
    console.log("Exception in requireListener: ", e);
    res.status(500);
    return res.json({
      message: "Error When trying to authenticate as listener",
    });
  }

  next();
}
