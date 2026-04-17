enum ModelType {
    INHERIT, // Inherit from global config
    PROGRAM, // Execute shell commands directly

    // LLM model types - prompt is used as the prompt / cli argument
    CLAUDE_CODE,
    OPENCODE
}

interface Model {
    type: ModelType;
    model: string;
}

interface Workflow {
    name: string;
    steps: Step[];
}

interface Step {
    name: string;
    description?: string;
    shouldCreateSummary: boolean; // If true, optionally check for summary details, else check for commit changes
    shouldCommitChanges: boolean; // If true, commit changes to the repository
}

interface TaskStep extends Step {
    type: 'task';
    prompt: string; // Command/script to execute for tasks
    model: Model;
}


/// === DECISIONS === ///

// Decisions evaluate as if/else-if: the first matching condition wins.

enum DecisionMode {
    FILE_EXISTS,                    // Check if a file (or glob) exists — returns 1 or 0
    FILE_CONTAINS,                  // Check if a file contains a string — returns 1 or 0
    READ_FILE,                      // Read file contents and parse as number
    JSON_KEY_VALUE,                 // Read a key path from a JSON file
    GREP,                           // Grep a pattern on files — returns match count
    SHELL,                          // Run a shell command — returns exit code
    READ_FILE_WITH_MODEL_DIGEST,    // Read file then have LLM digest to a decision
    USE_MODEL                       // Use an LLM to decide
}

interface DecisionBase extends Step {
    type: 'decision';
    decision: Decision[];
}

interface DecisionStepFileExists extends DecisionBase {
    mode: DecisionMode.FILE_EXISTS;
    modeInfo: {
        fileName: string;
    }
}

interface DecisionStepReadFile extends DecisionBase {
    mode: DecisionMode.READ_FILE;
    modeInfo: {
        fileName: string;
    }
}

interface DecisionStepReadFileWithDigest extends DecisionBase {
    mode: DecisionMode.READ_FILE_WITH_MODEL_DIGEST;
    modeInfo: {
        fileName: string;
        prompt: string; // Prompt to guide LLM analysis of file contents
    }
    model: Model;
}

interface DecisionStepFileContains extends DecisionBase {
    mode: DecisionMode.FILE_CONTAINS;
    modeInfo: {
        fileName: string;
        searchString: string;
    }
}

interface DecisionStepJsonKeyValue extends DecisionBase {
    mode: DecisionMode.JSON_KEY_VALUE;
    modeInfo: {
        fileName: string;
        keyPath: string; // Dot-separated path, e.g. "summary.count"
    }
}

interface DecisionStepGrep extends DecisionBase {
    mode: DecisionMode.GREP;
    modeInfo: {
        pattern: string;
        file: string; // Glob pattern for target files
    }
}

interface DecisionStepShell extends DecisionBase {
    mode: DecisionMode.SHELL;
    modeInfo: {
        command: string;
    }
}

interface DecisionStepUseModel extends DecisionBase {
    mode: DecisionMode.USE_MODEL;
    modeInfo: {
        prompt: string; // Prompt for LLM to make decision
    }
    model: Model;
}

type DecisionStep =
    | DecisionStepFileExists
    | DecisionStepFileContains
    | DecisionStepReadFile
    | DecisionStepJsonKeyValue
    | DecisionStepGrep
    | DecisionStepShell
    | DecisionStepReadFileWithDigest
    | DecisionStepUseModel;


interface Decision {
    operator: 'eq' | 'gt' | 'lt' | 'gte' | 'lte' | 'neq';
    value: number;
    action: 'CONTINUE' | 'STOP' | 'REPEAT_PREVIOUS_STEP' | 'JUMP_TO_STEP'; // NOTE: We should use JUMP to JUMP to end or smth, more so than to go back, going back = recursion = problem.
    destinationStep?: string; // Required when action is JUMP_TO_STEP - the name of the step to jump to
}