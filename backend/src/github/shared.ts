import { Octokit, App } from "octokit";
import { githubAppId, githubAppPrivateKey } from "../config/config";

export const initOctokit = (token?: string): Octokit => {
  if (token) {
    return new Octokit({
      auth: token,
    });
  } else {
    return new Octokit();
  }
}

export const initNewApp = () => {
  if (!githubAppId || !githubAppPrivateKey) {
    throw new Error("Incorrect settings");
  }
  return new App({
    appId: githubAppId, // Recon app
    privateKey: githubAppPrivateKey, // PK / Secret
  });
}

export const unauthorizedOctokit = new Octokit();
