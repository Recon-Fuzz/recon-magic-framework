enum ModelType {
    INHERIT, // Inherit from global config
    PROGRAM, // TODO: See if useful

    // Langchain Options // TODO: Likely never useful since we have to code them. May as well ship as separate programs.

    // NOTE: Likely to never use these
    // Cause we basically always run a program, either a Langchain Program or a CLI Toool. Either way we need to build a prompt with a prompt builder.
    
    // Prompt is used as prompt / cli arg
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

// TODO: A decision is a if | else if so we always go for first match, important to note as this can cause confusion!

enum DecisionMode {
    FILE_EXISTS, // Check if a file exists
    READ_FILE, // Read contents and decide on them
    READ_FILE_WITH_MODEL_DIGEST, // Have LLM digest down to the decision
    USE_MODEL // Use a model to decide
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

interface DecisionStepUseModel extends DecisionBase {
    mode: DecisionMode.USE_MODEL;
    modeInfo: {
        prompt: string; // Prompt for LLM to make decision
    }
    model: Model;
}

type DecisionStep = DecisionStepFileExists | DecisionStepReadFile | DecisionStepReadFileWithDigest | DecisionStepUseModel;


interface Decision {
    operator: 'eq' | 'gt' | 'lt' | 'gte' | 'lte' | 'neq';
    value: number;
    action: 'CONTINUE' | 'STOP' | 'REPEAT_PREVIOUS_STEP' | 'JUMP_TO_STEP'; // NOTE: We should use JUMP to JUMP to end or smth, more so than to go back, going back = recursion = problem.
    destinationStep?: string; // Required when action is JUMP_TO_STEP - the name of the step to jump to
}