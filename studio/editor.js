// Global state
let workflow = null;

// Create new empty workflow
function createNew() {
    workflow = {
        name: "New Workflow",
        steps: []
    };
    showEditor();
    renderSteps();
    updatePreview();
}

// Import workflow from JSON
function importWorkflow() {
    const json = document.getElementById('importJson').value;
    try {
        workflow = JSON.parse(json);
        showEditor();
        renderSteps();
        updatePreview();
    } catch (e) {
        alert('Invalid JSON: ' + e.message);
    }
}

// Show editor panel
function showEditor() {
    document.getElementById('editor').classList.remove('hidden');
    document.getElementById('workflowName').value = workflow.name;
}

// Add new step
function addStep(type) {
    const newStep = {
        name: `Step ${workflow.steps.length + 1}`,
        type: type,
        description: '',
        prompt: '',
        model: {
            type: 'CLAUDE_CODE',
            model: 'inherit'
        },
        shouldCreateSummary: false,
        shouldCommitChanges: true
    };

    if (type === 'decision') {
        newStep.mode = 'READ_FILE';
        newStep.modeInfo = { fileName: 'result.txt' };
        newStep.decision = [
            { operator: 'eq', value: 0, action: 'CONTINUE' }
        ];
    }

    workflow.steps.push(newStep);
    renderSteps();
    updatePreview();
}

// Remove step
function removeStep(index) {
    workflow.steps.splice(index, 1);
    renderSteps();
    updatePreview();
}

// Move step up
function moveStepUp(index) {
    if (index === 0) return;
    const temp = workflow.steps[index];
    workflow.steps[index] = workflow.steps[index - 1];
    workflow.steps[index - 1] = temp;
    renderSteps();
    updatePreview();
}

// Move step down
function moveStepDown(index) {
    if (index === workflow.steps.length - 1) return;
    const temp = workflow.steps[index];
    workflow.steps[index] = workflow.steps[index + 1];
    workflow.steps[index + 1] = temp;
    renderSteps();
    updatePreview();
}

// Render steps list
function renderSteps() {
    const container = document.getElementById('stepsList');
    if (!workflow || workflow.steps.length === 0) {
        container.innerHTML = '<p class="text-gray-500 text-sm">No steps yet. Click "Add Task" to get started.</p>';
        return;
    }

    container.innerHTML = workflow.steps.map((step, index) => `
        <div class="border rounded p-4 space-y-3">
            <div class="flex justify-between items-center">
                <h4 class="font-bold text-sm">Step ${index + 1}: ${step.type}</h4>
                <div class="space-x-1">
                    ${index > 0 ? `<button onclick="moveStepUp(${index})" class="px-2 py-1 text-xs bg-gray-200 rounded hover:bg-gray-300">↑</button>` : ''}
                    ${index < workflow.steps.length - 1 ? `<button onclick="moveStepDown(${index})" class="px-2 py-1 text-xs bg-gray-200 rounded hover:bg-gray-300">↓</button>` : ''}
                    <button onclick="removeStep(${index})" class="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700">✕</button>
                </div>
            </div>

            <input
                type="text"
                value="${step.name}"
                placeholder="Step name"
                class="w-full px-3 py-2 border rounded text-sm"
                oninput="workflow.steps[${index}].name = this.value; updatePreview()"
            />

            <input
                type="text"
                value="${step.description || ''}"
                placeholder="Description (optional)"
                class="w-full px-3 py-2 border rounded text-sm"
                oninput="workflow.steps[${index}].description = this.value; updatePreview()"
            />

            ${step.type === 'task' ? `
                <textarea
                    placeholder="Prompt"
                    class="w-full px-3 py-2 border rounded text-sm h-24"
                    oninput="workflow.steps[${index}].prompt = this.value; updatePreview()"
                >${step.prompt}</textarea>

                <div class="grid grid-cols-2 gap-2">
                    <select
                        class="px-3 py-2 border rounded text-sm"
                        onchange="workflow.steps[${index}].model.type = this.value; updatePreview()"
                    >
                        <option value="CLAUDE_CODE" ${step.model.type === 'CLAUDE_CODE' ? 'selected' : ''}>Claude Code</option>
                        <option value="PROGRAM" ${step.model.type === 'PROGRAM' ? 'selected' : ''}>Program</option>
                        <option value="OPENROUTER" ${step.model.type === 'OPENROUTER' ? 'selected' : ''}>OpenRouter</option>
                    </select>

                    <input
                        type="text"
                        value="${step.model.model}"
                        placeholder="Model"
                        class="px-3 py-2 border rounded text-sm"
                        oninput="workflow.steps[${index}].model.model = this.value; updatePreview()"
                    />
                </div>

                <div class="flex gap-4 text-sm">
                    <label class="flex items-center gap-2">
                        <input
                            type="checkbox"
                            ${step.shouldCreateSummary ? 'checked' : ''}
                            onchange="workflow.steps[${index}].shouldCreateSummary = this.checked; updatePreview()"
                        />
                        Create Summary
                    </label>
                    <label class="flex items-center gap-2">
                        <input
                            type="checkbox"
                            ${step.shouldCommitChanges ? 'checked' : ''}
                            onchange="workflow.steps[${index}].shouldCommitChanges = this.checked; updatePreview()"
                        />
                        Commit Changes
                    </label>
                </div>
            ` : `
                <div class="space-y-2">
                    <select
                        class="w-full px-3 py-2 border rounded text-sm"
                        onchange="workflow.steps[${index}].mode = this.value; updatePreview()"
                    >
                        <option value="READ_FILE" ${step.mode === 'READ_FILE' ? 'selected' : ''}>Read File</option>
                        <option value="READ_FILE_WITH_MODEL_DIGEST" ${step.mode === 'READ_FILE_WITH_MODEL_DIGEST' ? 'selected' : ''}>Read File with Model Digest</option>
                        <option value="USE_MODEL" ${step.mode === 'USE_MODEL' ? 'selected' : ''}>Use Model</option>
                    </select>

                    <input
                        type="text"
                        value="${step.modeInfo?.fileName || ''}"
                        placeholder="File name"
                        class="w-full px-3 py-2 border rounded text-sm"
                        oninput="workflow.steps[${index}].modeInfo = { fileName: this.value }; updatePreview()"
                    />

                    <div class="text-xs text-gray-600 mt-2">
                        <strong>Decisions:</strong>
                        ${step.decision.map((d, di) => `
                            <div class="flex gap-2 mt-1">
                                <select class="px-2 py-1 border rounded" onchange="workflow.steps[${index}].decision[${di}].operator = this.value; updatePreview()">
                                    <option value="eq" ${d.operator === 'eq' ? 'selected' : ''}>==</option>
                                    <option value="neq" ${d.operator === 'neq' ? 'selected' : ''}>!=</option>
                                    <option value="gt" ${d.operator === 'gt' ? 'selected' : ''}>&gt;</option>
                                    <option value="lt" ${d.operator === 'lt' ? 'selected' : ''}>&lt;</option>
                                    <option value="gte" ${d.operator === 'gte' ? 'selected' : ''}>≥</option>
                                    <option value="lte" ${d.operator === 'lte' ? 'selected' : ''}>≤</option>
                                </select>
                                <input type="number" value="${d.value}" class="px-2 py-1 border rounded w-20" onchange="workflow.steps[${index}].decision[${di}].value = parseFloat(this.value); updatePreview()" />
                                <select class="px-2 py-1 border rounded" onchange="workflow.steps[${index}].decision[${di}].action = this.value; updatePreview()">
                                    <option value="CONTINUE" ${d.action === 'CONTINUE' ? 'selected' : ''}>Continue</option>
                                    <option value="STOP" ${d.action === 'STOP' ? 'selected' : ''}>Stop</option>
                                    <option value="REPEAT_PREVIOUS_STEP" ${d.action === 'REPEAT_PREVIOUS_STEP' ? 'selected' : ''}>Repeat Previous</option>
                                </select>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `}
        </div>
    `).join('');
}

// Update preview
function updatePreview() {
    if (!workflow) return;

    workflow.name = document.getElementById('workflowName').value;
    document.getElementById('preview').textContent = JSON.stringify(workflow, null, 2);
}

// Export workflow
function exportWorkflow() {
    if (!workflow) {
        alert('No workflow to export');
        return;
    }

    const json = JSON.stringify(workflow, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${workflow.name.toLowerCase().replace(/\s+/g, '-')}.json`;
    a.click();
    URL.revokeObjectURL(url);
}
