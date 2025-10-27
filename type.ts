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

// TODO: A decision is a if | else if so we always go for first match, important to note as this can cause confusion!
interface DecisionStep extends Step {
    type: 'decision';
    decision: Decision[];
}

interface Decision {
    operator: 'eq' | 'gt' | 'lt' | 'gte' | 'lte' | 'neq';
    value: number;
    action: 'CONTINUE' | 'COUNTER_MINUS_ONE' | 'STOP';
}


// Metaprogramming necessary in order to pass refined context
// Ingest Context from file, inject context from function