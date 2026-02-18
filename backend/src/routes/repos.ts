import { Request, Response } from "express";
import express from "express";
import { onlyLoggedIn } from "../middleware/auth";
import { initOctokit } from "../github/shared";

const router = express.Router();
export default router;

/**
 * GET /repos/:orgName/:repoName/access
 * Check if the current user can access this repo
 */
router.get(
  "/:orgName/:repoName/access",
  onlyLoggedIn,
  async (req: Request, res: Response) => {
    const { orgName, repoName } = req.params;

    if (req.user.authenticatedBy !== "github") {
      return res.status(403).json({ error: "This endpoint requires GitHub OAuth authentication" });
    }

    try {
      const octokit = initOctokit(req.user.token);

      const { data: info } = await octokit.request("GET /repos/{owner}/{repo}", {
        owner: orgName,
        repo: repoName,
      });

      return res.json({
        message: "Repo access check",
        data: {
          canAccess: true,
          repoInfo: {
            name: info.name,
            fullName: info.full_name,
            defaultBranch: info.default_branch,
            private: info.private,
          },
        },
      });
    } catch (e: any) {
      // User doesn't have access - return canAccess: false
      if (e.status === 404 || e.status === 403) {
        return res.json({
          message: "Repo access check",
          data: { canAccess: false, repoInfo: null },
        });
      }
      console.error("Error checking repo access:", e?.message || e);
      if (e.status === 429 || e?.message?.includes("quota") || e?.message?.includes("rate limit")) {
        return res.status(429).json({ message: "GitHub API rate limit reached. Please wait a moment and try again.", data: {} });
      }
      return res.status(500).json({ message: e?.message || "Error checking repo access", data: {} });
    }
  }
);

/**
 * GET /repos/:orgName/:repoName/:branch/tree
 * List contents at a path (one level deep, like `ls`)
 * Query params:
 *   ?path=src/routes (optional, defaults to root)
 *   ?recursive=true (optional, returns full tree)
 */
router.get(
  "/:orgName/:repoName/:branch/tree",
  onlyLoggedIn,
  async (req: Request, res: Response) => {
    const { orgName, repoName, branch } = req.params;
    const path = (req.query.path as string) || "";
    const recursive = req.query.recursive === "true";

    if (req.user.authenticatedBy !== "github") {
      return res.status(403).json({ error: "This endpoint requires GitHub OAuth authentication" });
    }

    const octokit = initOctokit(req.user.token);

    try {
      const { data: refData } = await octokit.request(
        "GET /repos/{owner}/{repo}/commits/{ref}",
        { owner: orgName, repo: repoName, ref: branch }
      );

      const { data: treeData } = await octokit.request(
        "GET /repos/{owner}/{repo}/git/trees/{tree_sha}",
        { owner: orgName, repo: repoName, tree_sha: refData.sha, recursive: "true" }
      );

      if (recursive) {
        return res.json({
          message: "Full tree listing",
          data: {
            path: "/",
            branch,
            recursive: true,
            items: treeData.tree.map((item) => ({
              name: item.path!.split("/").pop()!,
              path: item.path!,
              type: item.type === "tree" ? "dir" : "file",
              size: item.size || 0,
              sha: item.sha!,
            })),
          },
        });
      }

      const normalizedPath = path.replace(/^\/|\/$/g, "");
      const pathPrefix = normalizedPath ? `${normalizedPath}/` : "";

      const items = treeData.tree
        .filter((item) => {
          if (!item.path) return false;
          if (!normalizedPath) return !item.path.includes("/");
          if (!item.path.startsWith(pathPrefix)) return false;
          return !item.path.slice(pathPrefix.length).includes("/");
        })
        .map((item) => ({
          name: item.path!.split("/").pop()!,
          path: item.path!,
          type: item.type === "tree" ? "dir" : "file",
          size: item.size || 0,
          sha: item.sha!,
        }))
        .sort((a, b) => {
          if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
          return a.name.localeCompare(b.name);
        });

      return res.json({
        message: "Directory listing",
        data: { path: normalizedPath || "/", branch, items },
      });
    } catch (e: any) {
      if (e.status === 404 || e.status === 403) {
        return res.status(e.status).json({ message: "Repository, branch, or path not found", data: {} });
      }
      console.error("Error fetching tree:", e?.message || e);
      if (e.status === 429 || e?.message?.includes("quota") || e?.message?.includes("rate limit")) {
        return res.status(429).json({ message: "GitHub API rate limit reached. Please wait a moment and try again.", data: {} });
      }
      return res.status(500).json({ message: e?.message || "Error fetching tree", data: {} });
    }
  }
);

/**
 * GET /repos/:orgName/:repoName/:branch/file
 * Get contents of a single file
 * Query param: ?path=src/index.ts (required)
 */
router.get(
  "/:orgName/:repoName/:branch/file",
  onlyLoggedIn,
  async (req: Request, res: Response) => {
    const { orgName, repoName, branch } = req.params;
    const path = req.query.path as string;

    if (!path) {
      return res.status(400).json({ message: "Missing required query param: path", data: {} });
    }

    if (req.user.authenticatedBy !== "github") {
      return res.status(403).json({ error: "This endpoint requires GitHub OAuth authentication" });
    }

    const octokit = initOctokit(req.user.token);

    try {
      const { data } = await octokit.request(
        "GET /repos/{owner}/{repo}/contents/{path}",
        { owner: orgName, repo: repoName, path, ref: branch }
      );

      if (Array.isArray(data)) {
        return res.status(400).json({ message: "Path is a directory, not a file", data: {} });
      }

      if (data.type !== "file") {
        return res.status(400).json({ message: "Path is not a file", data: {} });
      }

      let content = "";
      let encoding = "utf-8";

      if (data.content) {
        try {
          content = Buffer.from(data.content, "base64").toString("utf-8");
        } catch {
          content = data.content;
          encoding = "base64";
        }
      }

      return res.json({
        message: "File contents",
        data: {
          path: data.path,
          name: data.name,
          size: data.size,
          sha: data.sha,
          content,
          encoding,
        },
      });
    } catch (e: any) {
      if (e.status === 404 || e.status === 403) {
        return res.status(e.status).json({ message: "File not found or no access", data: {} });
      }
      console.error("Error fetching file:", e?.message || e);
      if (e.status === 429 || e?.message?.includes("quota") || e?.message?.includes("rate limit")) {
        return res.status(429).json({ message: "GitHub API rate limit reached. Please wait a moment and try again.", data: {} });
      }
      return res.status(500).json({ message: e?.message || "Error fetching file", data: {} });
    }
  }
);
