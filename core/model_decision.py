"""
Model-based decision execution using structured outputs.

This module implements LLM-based decision making with automatic validation
using LangChain's structured output capabilities and Pydantic schemas.
"""

from typing import Any, Type
from pydantic import BaseModel, Field, create_model


def create_decision_schema(valid_values: list[float]) -> Type[BaseModel]:
    """
    Create a dynamic Pydantic schema with Literal types for valid decision values.

    This ensures the LLM can only return values that match the decision options.

    Args:
        valid_values: List of valid numeric decision values

    Returns:
        A Pydantic BaseModel class with Literal type constraints
    """
    from typing import Literal

    # Convert to tuple for Literal type
    valid_values_tuple = tuple(valid_values)

    # Create the Literal type
    # Note: For Python typing, we need to handle this dynamically
    literal_type = Literal[valid_values_tuple]  # type: ignore

    class DecisionOutput(BaseModel):
        """Structured output for LLM-based decisions."""
        selected_value: float = Field(
            description=f"MUST be exactly one of these values: {valid_values}. "
                       f"Do not invent new values. Select the option that best matches the situation."
        )
        reasoning: str = Field(
            description="Brief explanation (1-2 sentences) for why you selected this value"
        )

        # Add validator to ensure value is in valid_values
        def __init__(self, **data: Any):
            super().__init__(**data)
            if self.selected_value not in valid_values:
                raise ValueError(
                    f"selected_value must be one of {valid_values}, got {self.selected_value}"
                )

    return DecisionOutput


def format_decision_options(decisions: list[Any]) -> str:
    """
    Format decision options for the prompt.

    Args:
        decisions: List of Decision objects with value, action, and destinationStep

    Returns:
        Formatted string describing each decision option
    """
    lines = []
    for decision in decisions:
        action_desc = decision.action
        if decision.destinationStep:
            action_desc += f" (Jump to: {decision.destinationStep})"
        lines.append(f"  • {decision.value} - {action_desc}")

    return "\n".join(lines)


def create_decision_prompt(base_prompt: str, decisions: list[Any]) -> str:
    """
    Create a two-part prompt with explicit option constraints.

    Part 1: The actual task/question for the LLM
    Part 2: Explicit enumeration of valid options with instruction to ONLY return those values

    Args:
        base_prompt: The main prompt describing the decision task
        decisions: List of Decision objects

    Returns:
        Complete prompt with task and explicit option constraints
    """
    valid_values = [d.value for d in decisions]

    prompt_parts = [
        base_prompt,
        "\n\n---\n",
        "IMPORTANT: You must select EXACTLY ONE of the following numeric values:\n\n",
        format_decision_options(decisions),
        f"\n\nYou MUST return one of these exact values: {valid_values}",
        "\nDo not invent new values. Choose the option that best matches the situation."
    ]

    return "".join(prompt_parts)


def perform_decision_with_model(
    decisions: list[Any],
    prompt: str,
    model_config: Any
) -> tuple[float, str]:
    """
    Execute a model-based decision using an agent with file reading capabilities.

    This function creates an agent with access to file reading tools and uses
    structured outputs to ensure the LLM returns only valid decision values.

    Args:
        decisions: List of Decision objects with value, action, and destinationStep
        prompt: The base prompt describing what decision to make
        model_config: Model configuration object with type and model name

    Returns:
        tuple[float, str]: (selected_value, reasoning)

    Example:
        >>> decisions = [
        ...     Decision(value=0.0, action="STOP", operator="eq"),
        ...     Decision(value=1.0, action="CONTINUE", operator="eq")
        ... ]
        >>> value, reasoning = perform_decision_with_model(
        ...     decisions, "Should we continue?", model_config
        ... )
    """
    import os
    from langchain_openai import ChatOpenAI
    from langchain_core.tools import tool
    from langgraph.prebuilt import create_react_agent
    from pathlib import Path

    # Extract valid decision values
    valid_values = [d.value for d in decisions]

    # Create the dynamic Pydantic schema
    DecisionSchema = create_decision_schema(valid_values)

    # Define file reading tool
    @tool
    def read_file(file_path: str) -> str:
        """
        Read the contents of a file from the filesystem.

        Args:
            file_path: Path to the file to read (can be absolute or relative)

        Returns:
            The contents of the file as a string
        """
        try:
            # Get the repo path - use RECON_FOUNDRY_ROOT for monorepos, fall back to RECON_REPO_PATH
            repo_path = os.environ.get('RECON_FOUNDRY_ROOT') or os.environ.get('RECON_REPO_PATH') or '.'
            base_path = Path(repo_path)

            path = Path(file_path)
            if not path.is_absolute():
                # Make relative paths relative to the repo
                path = base_path / file_path

            if not path.exists():
                # Try to find the file using glob pattern within the repo
                matches = list(base_path.glob(f"**/{file_path}"))
                if not matches:
                    return f"Error: File not found: {file_path}"
                path = matches[0]

            content = path.read_text()
            return content
        except Exception as e:
            return f"Error reading file: {str(e)}"

    # Initialize the LLM using OpenRouter
    # OpenRouter allows you to choose from multiple providers (Anthropic, OpenAI, etc.)
    default_model = "openai/gpt-4o"  # Default to GPT-4o
    model_name = getattr(model_config, 'model', default_model) if model_config else default_model

    # Handle "inherit" as default model
    if model_name == "inherit":
        model_name = default_model

    llm = ChatOpenAI(
        model=model_name,  # e.g., "anthropic/claude-3.5-sonnet", "openai/gpt-4o", etc.
        temperature=0,  # Use deterministic output for decisions
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv('OPENAI_API_KEY')
    )

    # Create the full prompt with decision constraints
    full_prompt = create_decision_prompt(prompt, decisions)

    # Create agent with tools for exploration
    tools = [read_file]
    agent = create_react_agent(llm, tools)

    print(f"🤖 Asking agent to make decision with file reading capability...")
    print(f"📋 Valid options: {valid_values}")

    # Run agent to gather information
    agent_result = agent.invoke({"messages": [("user", full_prompt)]})

    # Extract the final message
    final_message = agent_result["messages"][-1].content

    # Use structured output to get the final decision
    structured_llm = llm.with_structured_output(DecisionSchema)
    result = structured_llm.invoke(final_message)

    print(f"✓ Agent selected: {result.selected_value}")
    print(f"💭 Reasoning: {result.reasoning}")

    return (result.selected_value, result.reasoning)
