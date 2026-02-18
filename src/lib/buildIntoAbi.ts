import { execFile } from "child_process";

// Given a CMD execute it and return the logs
function exec(cmd: string, args: string[] = [], options: object = {}): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile(cmd, args, options, (error, stdout, stderr) => {
      if (error) {
        reject(error);
      } else {
        const output = stdout ? stdout : stderr;
        console.log(output);
        resolve(output.trim());
      }
    });
  });
}

// Given a Authenticated Clone URL, branch and other settings, clone, then build and return the ABI Information
export default async function buildAndReturnABI(
  url: string, // We expect the URL to contain authentication keys if necessary
  out: string, // out path, defaults to "out"
  branch?: string,
  path?: string,
  defaultpreProcess = "yarn install --ignore-scripts && git submodule update --init --recursive && forge install",
  postprocess = "true"
): Promise<{ name: any; abi: any; abiPath: any }[]> {
  // TODO 0XSI
  // Ultimately this should be in its own docker image
  const directory = await exec(`mktemp`, ["-d"]);

  // Add a way to throw after 10 minutes
  const TIMEOUT_REVERT = 10 * 60 * 1000; // 10 minutes
  // const TIMEOUT_REVERT = 1 * 1000; // 1 seconds // NOTE: Debug

  // TODO: use this: https://stackoverflow.com/questions/52059034/setting-timeout-for-async-function-to-stop-running-after-x-seconds-if-not-done-b

  // TODO: Missing extra commands to compile
  // Without extra commands we're fucked
  // To avoid RCE
  // Directory (string, string, string)
  // Use yarn -> This may allow RCE
  // Load submodules?
  // Use forge install
  // TODO: Issue when installing something with Chimera?
  const customPath = path === "." ? directory : `${directory}/${path}`;

  let workPromise;
  if (branch) {
    const params = [branch, url, directory, customPath, `${postprocess}`]
    // Fetch with branch
    workPromise = exec(
      "./build_project.sh",
      params
    );
  } else {
    workPromise = executeCommands(url, directory, defaultpreProcess, postprocess);
  }



  const data = await Promise.race([
    workPromise,
    new Promise((resolve, reject) => {
      // Reject after TIMEOUT_REVERT seconds
      setTimeout(() => resolve("Done"), TIMEOUT_REVERT); // Basically we resolve this and cause the lines below to fail
    }),
  ]); // Either resolves workPromise, or throws due to timeout

  // Insight into build fails
  console.log(`BUILDER_PREP: , ${data}`);

  // TODO: Can we get the Commit we built at here?
  // TODO: Prob need a local playground to help debug this

  // TODO: Given a folder, generate the abiData
  // Given that data, we can upload it to the API manually

  // Wrap the output in a try/catch
  let output = "";

  // Extra check that `out` isn't empty
  if (out !== "") {
    // If the output dir doesn't exist we fail the build
    try {
      // Look in the tmp dir
      // for a custom out the user MUST specify the entire path
      // Sometimes the target dir is nested deeper than the foundry output (which is always shallow in the tmp dir)
      const params = [`${customPath}/${out}`, "-type", "f", "-name", "*.json"]
      output = await exec("find", params);
    } catch (e) {
      console.log("Error in ABI builder", e);
    }
  }

  // If output dir not found we return early
  if (output == "") {
    return [];
  }

  // Only execute if the output folder has been found
  const contractNames = output
    .split("\n")
    .map((line) => line.replace(/.*\//, "").replace(".json", ""))
    .filter((line) => line);
  const contracts = await Promise.all(
    contractNames.map(async (name) => {
      const outParams = `find ${customPath}/${out} -type f -name ${name}.json -exec jq -rc '.abi' {} \\;`;
      const output = await exec("sh", ["-c", outParams]);

      const abiPathParams = `find ${customPath}/${out} -type f -name ${name}.json -exec jq -rc '.ast.absolutePath' {} \\;`;
      const abiPath = await exec("sh", ["-c", abiPathParams]);

      try {
        console.log("name", name);
        const abi = output ? JSON.parse(output) : undefined;
        console.log(name, abi);
        /**
         * TODO
         *  We could get `compilationTarget` to always get the name
         *
          "compilationTarget": {
            "lib/forge-std/src/StdMath.sol": "stdMath"
          },
          https://docs.soliditylang.org/en/latest/metadata.html#:~:text=created%20for.%0A%20%20%20%20%22-,compilationTarget,-%22%3A%20%7B
         */
        return { name, abi, abiPath };
      } catch (e) {
        console.log("error", e);
      }
    })
  );

  console.log("contracts length", contracts.length);
  const rmParams = ["-rf", directory]
  await exec(`rm`, rmParams);
  // @ts-ignore
  return contracts.filter((contract) => contract?.abi?.length > 0);
}

async function executeCommands(url: string, directory: string, defaultpreProcess: string, postprocess: string): Promise<string> {
  try {
    console.log("Cloning ....")
    // 1. Clone the repository
    await exec("git", ["clone", url, directory]);

    // 2. Specify the working directory for the next commands
    const options = { cwd: directory };

    console.log("Running pre-process command ....")
    // 3. Run the pre-process command
    await exec("sh", ["-c", defaultpreProcess], options);

    console.log("Building ....")
    // 4. Run the `forge build --ast` command
    await exec("forge", ["build", "--ast"], options);

    console.log("Running post-process command ....")
    // 5. Run the post-process command
    await exec("sh", ["-c", postprocess], options);

    return "Execution completed successfully";
  } catch (error) {
    throw new Error(`Execution failed: ${error}`);
  }
}
