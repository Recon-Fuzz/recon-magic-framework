enum ModelType {
    INHERIT, // Inherit from global config
    PROGRAM, // TODO: See if useful

    // Langchain Options // TODO: Likely never useful since we have to code them. May as well ship as separate programs.

    // NOTE: Likely to never use these
    // Cause we basically always run a program, either a Langchain Program or a CLI Toool. Either way we need to build a prompt with a prompt builder.
    
    // Prompt is used as prompt / cli arg
    CLAUDE_CODE,
    OPENROUTER
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
    prompt: string;
    model: Model;
    shouldCreateSummary: boolean; // If true, optionally check for summary details, else check for commit changes
    shouldCommitChanges: boolean; // If true, commit changes to the repository
}

interface TaskStep extends Step {
    type: 'task';
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
    }
}

interface DecisionStepUseModel extends DecisionBase {
    mode: DecisionMode.USE_MODEL;
    modeInfo: {
        prompt: string;
    }
}

type DecisionStep = DecisionStepReadFile | DecisionStepReadFileWithDigest | DecisionStepUseModel;


interface Decision {
    operator: 'eq' | 'gt' | 'lt' | 'gte' | 'lte' | 'neq';
    value: number;
    action: 'CONTINUE' | 'STOP' // | 'JUMP_TO_STEP'; TODO: Add later, also this makes code harder to reason about.
}