# Save Echidna Logs Tool

CLI tool to capture and save Echidna fuzzing logs for later analysis by workflow agents.

## Purpose

This tool extracts Echidna output from the most recent workflow run and saves it in both raw and structured formats to the `magic/` directory. This makes it easy for subsequent workflow agents to analyze failures and fix issues.

## Installation

The tool is automatically installed when you install the recon-magic framework:

```bash
uv pip install -e .
# or
pip install -e .
```

After installation, the `save-echidna-logs` command will be available globally.

## Usage

### Basic Usage

```bash
save-echidna-logs
```

This will:
1. Search for the most recent Echidna log file in `./logs/`
2. Parse the log content to extract errors and failed tests
3. Save raw output to `./magic/echidna-output.txt`
4. Save structured JSON to `./magic/echidna-summary.json`

### Custom Output Directory

```bash
save-echidna-logs --output-dir ./custom-output
# or
save-echidna-logs -o ./custom-output
```

### In Workflows

Add as a PROGRAM step in your workflow JSON:

```json
{
  "name": "Save Echidna Logs",
  "type": "task",
  "description": "Save Echidna output logs for analysis",
  "prompt": "save-echidna-logs",
  "model": {
    "type": "PROGRAM",
    "model": "inherit"
  },
  "shouldCreateSummary": false,
  "shouldCommitChanges": true
}
```

## Output Files

### `magic/echidna-output.txt`

Raw output from the Echidna run, exactly as it appeared in the log file. Useful for:
- Reading complete context
- Debugging formatting issues
- Manual review

### `magic/echidna-summary.json`

Structured JSON with parsed information:

```json
{
  "raw_output": "...",
  "success": true,
  "failed_tests": [
    "test_invariant_balance FAILED",
    "test_access_control failed!"
  ],
  "errors": [
    "Error: VM execution error",
    "error: contract deployment failed"
  ],
  "coverage_info": null
}
```

## How It Works

1. **Log Discovery**: Searches `./logs/` directory for files matching `*echidna*.log`
2. **Latest Selection**: Chooses the most recently modified log file
3. **Parsing**: Extracts:
   - Success/failure status
   - Failed test names
   - Error messages
   - Coverage information (if available)
4. **Output**: Writes both raw and structured data to the magic directory

## Example Workflow

See `workflows/workflow-fuzzing-setup.json` for a complete example:

1. **Run Echidna** - Executes Echidna fuzzing
2. **Save Logs** - This tool captures and saves output
3. **Check Success** - Decision point based on echidna/ directory
4. **Fix Issues** - Agent reads saved logs and fixes problems

## Integration with Agents

After saving logs, reference them in agent prompts:

```json
{
  "prompt": "Echidna failed. Read magic/echidna-output.txt for raw output and magic/echidna-summary.json for parsed errors. Analyze and fix the issues found."
}
```

The structured JSON makes it easy for agents to:
- Quickly identify if the run succeeded
- List all failed tests
- Extract specific error messages
- Focus on relevant issues

## Troubleshooting

### "No Echidna log files found"

- Ensure Echidna has run in a previous workflow step
- Check that logs are being saved to `./logs/` directory
- Verify the log filename contains "echidna" (case-insensitive)

### Empty or missing output

- Confirm the previous Echidna step completed
- Check file permissions on the logs directory
- Verify the magic directory can be created/written to

### Old logs being captured

The tool always captures the **most recent** log file. If you need a specific run:
1. Clean old logs from `./logs/`
2. Run Echidna again
3. Run this tool immediately after

## Related Tools

- `extract-target-functions` - Extracts targeted functions from test files
- `order-prerequisite-func` - Orders functions by prerequisite count
- `touched-function-identifier` - Identifies functions touched during fuzzing
- `covg-eval` - Evaluates fuzzing coverage

## License

Part of the recon-magic-framework project.
