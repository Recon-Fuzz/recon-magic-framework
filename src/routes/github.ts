import { Request, Response } from "express";
import express from "express";
import { onlyLoggedIn, requireProOrg } from "../middleware/auth";
import { fetchAllSolidityFiles } from "../github/repos";
import { getAppAccessTokenForRepoIfUserHasAccess } from "../github/installations";


const router = express.Router();
export default router;

router.get("/:orgName/:repoName/:branch",
    onlyLoggedIn,
    requireProOrg,
    async (req: Request, res: Response) => {

    const {orgName, repoName} = req.params
    let {branch} = req.params

    if(!branch) {
        branch = "main"
    }


    const token = await getAppAccessTokenForRepoIfUserHasAccess(
      req.headers.authorization!, // TODO: We likely want to standardize this
      orgName,
      repoName
    )

    try {
      const campaigns = await fetchAllSolidityFiles(
        orgName,
        repoName,
        branch,
        token || undefined
      );

      return res.json({
        message: "All Solidity for your Repo",
        data: campaigns,
      });
    } catch (e) {
      console.error("error fetching all solidity files:", e);
      res.status(500);
      return res.json({ message: "Error fetching all solidity files", data: {} });
    }
});
