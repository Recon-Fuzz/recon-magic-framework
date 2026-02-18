import axios from "axios";

// Given org, repo and branch, make the name to identify a specific repo
export function makeAbiIdentifier(
  orgName: string,
  repoName: string,
  branch: string
) {
  return `${orgName}_${repoName}_${branch}`;
}

export const getLogs = async (logsUrl: string) => {
  if (!logsUrl) {
    throw new Error("No logs url provided");
  }
  console.log("Fetching logs from ....", logsUrl);
  const fetchLogs = await axios({
    method: "GET",
    url: logsUrl,
  });
  if (!fetchLogs) {
    throw new Error("Failed to fetch logs");
  }

  return {
    logs: fetchLogs.data,
  }
}
