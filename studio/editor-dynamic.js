// Dynamic workflow editor that auto-generates from type.ts

// Global state
let workflow = null;
let parsedTypes = null;
let formGenerator = null;

// Load and parse type.ts
async function loadTypes() {
    try {
        const response = await fetch('/type.ts');
        const typeCode = await response.text();

        const parser = new TypeParser(typeCode);
        parsedTypes = parser.parse();
        formGenerator = new FormGenerator(parsedTypes);

        console.log('✅ Types loaded:', parsedTypes);
        console.log('📋 Interfaces:', Object.keys(parsedTypes.interfaces));
        console.log('🔢 Enums:', Object.keys(parsedTypes.enums));

        // Enable UI
        document.getElementById('loadingTypes').classList.add('hidden');
        document.getElementById('mainUI').classList.remove('hidden');

    } catch (error) {
        console.error('Failed to load types:', error);
        alert('Failed to load type.ts: ' + error.message);
    }
}

// Create new empty workflow
function createNew() {
    workflow = {
        name: "New Workflow",
        steps: []
    };
    showEditor();
    renderWorkflow();
    updatePreview();
}

// Import workflow from JSON
function importWorkflow() {
    const json = document.getElementById('importJson').value;
    try {
        workflow = JSON.parse(json);
        showEditor();
        renderWorkflow();
        updatePreview();
    } catch (e) {
        alert('Invalid JSON: ' + e.message);
    }
}

// Show editor panel
function showEditor() {
    document.getElementById('editor').classList.remove('hidden');
}

// Render entire workflow
function renderWorkflow() {
    // Render workflow name
    document.getElementById('workflowName').value = workflow.name;

    // Render steps
    renderSteps();
}

// Add new step
function addStep(type) {
    const stepTemplate = type === 'task' ? {
        type: 'task',
        name: `Step ${workflow.steps.length + 1}`,
        description: '',
        prompt: '',
        model: {
            type: 'CLAUDE_CODE',
            model: 'inherit'
        },
        shouldCreateSummary: false,
        shouldCommitChanges: true
    } : {
        type: 'decision',
        name: `Decision ${workflow.steps.length + 1}`,
        description: '',
        mode: 'READ_FILE',
        modeInfo: {
            fileName: 'result.txt'
        },
        decision: [
            { operator: 'eq', value: 0, action: 'CONTINUE' }
        ],
        prompt: 'Ignored',
        model: {
            type: 'PROGRAM',
            model: 'IGNORED'
        },
        shouldCreateSummary: false,
        shouldCommitChanges: false
    };

    workflow.steps.push(stepTemplate);
    renderSteps();
    updatePreview();
}

// Remove step
function removeStep(index) {
    workflow.steps.splice(index, 1);
    renderSteps();
    updatePreview();
}

// Move step
function moveStepUp(index) {
    if (index === 0) return;
    [workflow.steps[index], workflow.steps[index - 1]] = [workflow.steps[index - 1], workflow.steps[index]];
    renderSteps();
    updatePreview();
}

function moveStepDown(index) {
    if (index === workflow.steps.length - 1) return;
    [workflow.steps[index], workflow.steps[index + 1]] = [workflow.steps[index + 1], workflow.steps[index]];
    renderSteps();
    updatePreview();
}

// Render steps with dynamic forms
function renderSteps() {
    const container = document.getElementById('stepsList');

    if (!workflow || workflow.steps.length === 0) {
        container.innerHTML = '<p class="text-gray-500 text-sm">No steps yet. Click "Add Task" to get started.</p>';
        return;
    }

    container.innerHTML = workflow.steps.map((step, index) => {
        // Determine which interface to use
        const interfaceName = step.type === 'task' ? 'TaskStep' : 'DecisionStep';
        const interfaceProps = parsedTypes.interfaces[interfaceName] || [];

        return `
            <div class="border rounded p-4 space-y-3">
                <div class="flex justify-between items-center">
                    <h4 class="font-bold text-sm">Step ${index + 1}: ${step.type}</h4>
                    <div class="space-x-1">
                        ${index > 0 ? `<button onclick="moveStepUp(${index})" class="px-2 py-1 text-xs bg-gray-200 rounded hover:bg-gray-300">↑</button>` : ''}
                        ${index < workflow.steps.length - 1 ? `<button onclick="moveStepDown(${index})" class="px-2 py-1 text-xs bg-gray-200 rounded hover:bg-gray-300">↓</button>` : ''}
                        <button onclick="removeStep(${index})" class="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700">✕</button>
                    </div>
                </div>

                ${generateStepForm(step, index)}
            </div>
        `;
    }).join('');
}

// Generate form for a step
function generateStepForm(step, index) {
    if (!formGenerator) {
        console.error('Form generator not ready');
        return '<p class="text-red-500">Form generator not ready</p>';
    }

    // Get specific interface (which already extends Step, so includes all fields)
    const specificInterface = step.type === 'task' ? 'TaskStep' : 'DecisionBase';
    const allProps = parsedTypes.interfaces[specificInterface] || [];
    console.log(`Step ${index}: Found ${allProps.length} props for ${specificInterface}`);

    // Filter out fields we handle specially
    const skipFields = ['type', 'decision', 'mode', 'modeInfo'];
    const regularProps = allProps.filter(p => !skipFields.includes(p.name));

    return `
        <div class="space-y-3">
            ${regularProps.map(prop => {
                const value = step[prop.name];
                return generateFieldHtml(prop, index, value);
            }).join('')}

            ${step.type === 'decision' ? renderDecisionModeFields(step, index) : ''}
            ${step.type === 'decision' ? renderDecisionRules(step, index) : ''}
        </div>
    `;
}

// Generate HTML for a field
function generateFieldHtml(prop, stepIndex, currentValue) {
    const fieldInfo = formGenerator.parser.getFieldInfo(prop.type);

    switch (fieldInfo.kind) {
        case 'primitive':
            if (prop.type === 'boolean') {
                return `
                    <label class="flex items-center gap-2 text-sm">
                        <input
                            type="checkbox"
                            ${currentValue ? 'checked' : ''}
                            onchange="updateStepField(${stepIndex}, '${prop.name}', this.checked)"
                        />
                        ${formatLabel(prop.name)}
                    </label>
                `;
            } else if (prop.type === 'number') {
                return `
                    <div>
                        <label class="block text-sm font-medium mb-1">${formatLabel(prop.name)}</label>
                        <input
                            type="number"
                            value="${currentValue || ''}"
                            class="w-full px-3 py-2 border rounded text-sm"
                            oninput="updateStepField(${stepIndex}, '${prop.name}', parseFloat(this.value))"
                        />
                    </div>
                `;
            } else {
                // String or textarea for long text
                const isLongText = prop.name === 'prompt' || prop.name === 'description';
                return `
                    <div>
                        <label class="block text-sm font-medium mb-1">${formatLabel(prop.name)}</label>
                        ${isLongText ? `
                            <textarea
                                class="w-full px-3 py-2 border rounded text-sm h-24"
                                oninput="updateStepField(${stepIndex}, '${prop.name}', this.value)"
                            >${currentValue || ''}</textarea>
                        ` : `
                            <input
                                type="text"
                                value="${currentValue || ''}"
                                placeholder="${prop.optional ? '(optional)' : ''}"
                                class="w-full px-3 py-2 border rounded text-sm"
                                oninput="updateStepField(${stepIndex}, '${prop.name}', this.value)"
                            />
                        `}
                    </div>
                `;
            }

        case 'enum':
            return `
                <div>
                    <label class="block text-sm font-medium mb-1">${formatLabel(prop.name)}</label>
                    <select
                        class="w-full px-3 py-2 border rounded text-sm"
                        onchange="updateStepField(${stepIndex}, '${prop.name}', this.value)"
                    >
                        ${fieldInfo.values.map(v => `
                            <option value="${v}" ${currentValue === v ? 'selected' : ''}>${v}</option>
                        `).join('')}
                    </select>
                </div>
            `;

        case 'interface':
            // Render nested object (like Model)
            const nestedProps = fieldInfo.properties;
            return `
                <div class="border-l-2 border-blue-300 pl-3">
                    <h5 class="text-xs font-semibold text-gray-600 mb-2">${formatLabel(prop.name)}</h5>
                    ${nestedProps.map(nestedProp => {
                        const nestedValue = currentValue?.[nestedProp.name];
                        return generateNestedFieldHtml(nestedProp, stepIndex, prop.name, nestedValue);
                    }).join('')}
                </div>
            `;

        default:
            return `<p class="text-xs text-gray-500">Unknown type: ${prop.type}</p>`;
    }
}

// Generate nested field (e.g., model.type)
function generateNestedFieldHtml(prop, stepIndex, parentName, currentValue) {
    const fieldInfo = formGenerator.parser.getFieldInfo(prop.type);
    console.log(`Nested field ${parentName}.${prop.name}: type=${prop.type}, kind=${fieldInfo.kind}`, fieldInfo);

    if (fieldInfo.kind === 'enum') {
        return `
            <div class="mb-2">
                <label class="block text-xs font-medium mb-1">${formatLabel(prop.name)}</label>
                <select
                    class="w-full px-2 py-1 border rounded text-xs"
                    onchange="updateNestedField(${stepIndex}, '${parentName}', '${prop.name}', this.value)"
                >
                    ${fieldInfo.values.map(v => `
                        <option value="${v}" ${currentValue === v ? 'selected' : ''}>${v}</option>
                    `).join('')}
                </select>
            </div>
        `;
    } else {
        return `
            <div class="mb-2">
                <label class="block text-xs font-medium mb-1">${formatLabel(prop.name)}</label>
                <input
                    type="text"
                    value="${currentValue || ''}"
                    class="w-full px-2 py-1 border rounded text-xs"
                    oninput="updateNestedField(${stepIndex}, '${parentName}', '${prop.name}', this.value)"
                />
            </div>
        `;
    }
}

// Render decision mode and modeInfo fields
function renderDecisionModeFields(step, stepIndex) {
    const modes = ['READ_FILE', 'READ_FILE_WITH_MODEL_DIGEST', 'USE_MODEL', 'FILE_EXISTS'];

    return `
        <div>
            <label class="block text-sm font-medium mb-1">Decision Mode</label>
            <select
                class="w-full px-3 py-2 border rounded text-sm"
                onchange="updateStepField(${stepIndex}, 'mode', this.value)"
            >
                ${modes.map(m => `
                    <option value="${m}" ${step.mode === m ? 'selected' : ''}>${m}</option>
                `).join('')}
            </select>
        </div>
        <div>
            <label class="block text-sm font-medium mb-1">File Name</label>
            <input
                type="text"
                value="${step.modeInfo?.fileName || ''}"
                placeholder="e.g., CRITICAL_STOP.MD"
                class="w-full px-3 py-2 border rounded text-sm"
                oninput="updateStepField(${stepIndex}, 'modeInfo', { fileName: this.value })"
            />
        </div>
    `;
}

// Render decision rules (array handling)
function renderDecisionRules(step, stepIndex) {
    if (!step.decision) return '';

    return `
        <div class="border-t pt-3">
            <div class="flex justify-between items-center mb-2">
                <h5 class="text-sm font-semibold">Decision Rules</h5>
                <button
                    onclick="addDecisionRule(${stepIndex})"
                    class="px-2 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700"
                >
                    + Rule
                </button>
            </div>
            ${step.decision.map((rule, ruleIndex) => `
                <div class="flex gap-2 mb-2 items-center">
                    <select
                        class="px-2 py-1 border rounded text-xs"
                        onchange="updateDecisionRule(${stepIndex}, ${ruleIndex}, 'operator', this.value)"
                    >
                        <option value="eq" ${rule.operator === 'eq' ? 'selected' : ''}>=</option>
                        <option value="neq" ${rule.operator === 'neq' ? 'selected' : ''}>!=</option>
                        <option value="gt" ${rule.operator === 'gt' ? 'selected' : ''}>&gt;</option>
                        <option value="lt" ${rule.operator === 'lt' ? 'selected' : ''}>&lt;</option>
                        <option value="gte" ${rule.operator === 'gte' ? 'selected' : ''}>≥</option>
                        <option value="lte" ${rule.operator === 'lte' ? 'selected' : ''}>≤</option>
                    </select>
                    <input
                        type="number"
                        value="${rule.value}"
                        class="px-2 py-1 border rounded text-xs w-20"
                        oninput="updateDecisionRule(${stepIndex}, ${ruleIndex}, 'value', parseFloat(this.value))"
                    />
                    <select
                        class="px-2 py-1 border rounded text-xs flex-1"
                        onchange="updateDecisionRule(${stepIndex}, ${ruleIndex}, 'action', this.value)"
                    >
                        <option value="CONTINUE" ${rule.action === 'CONTINUE' ? 'selected' : ''}>Continue</option>
                        <option value="STOP" ${rule.action === 'STOP' ? 'selected' : ''}>Stop</option>
                        <option value="REPEAT_PREVIOUS_STEP" ${rule.action === 'REPEAT_PREVIOUS_STEP' ? 'selected' : ''}>Repeat Previous</option>
                    </select>
                    <button
                        onclick="removeDecisionRule(${stepIndex}, ${ruleIndex})"
                        class="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700"
                    >✕</button>
                </div>
            `).join('')}
        </div>
    `;
}

// Update handlers
function updateStepField(index, fieldName, value) {
    workflow.steps[index][fieldName] = value;
    updatePreview();
}

function updateNestedField(index, parentName, fieldName, value) {
    if (!workflow.steps[index][parentName]) {
        workflow.steps[index][parentName] = {};
    }
    workflow.steps[index][parentName][fieldName] = value;
    updatePreview();
}

function updateDecisionRule(stepIndex, ruleIndex, field, value) {
    workflow.steps[stepIndex].decision[ruleIndex][field] = value;
    updatePreview();
}

function addDecisionRule(stepIndex) {
    if (!workflow.steps[stepIndex].decision) {
        workflow.steps[stepIndex].decision = [];
    }
    workflow.steps[stepIndex].decision.push({
        operator: 'eq',
        value: 0,
        action: 'CONTINUE'
    });
    renderSteps();
    updatePreview();
}

function removeDecisionRule(stepIndex, ruleIndex) {
    workflow.steps[stepIndex].decision.splice(ruleIndex, 1);
    renderSteps();
    updatePreview();
}

// Update preview
function updatePreview() {
    if (!workflow) return;
    workflow.name = document.getElementById('workflowName').value;
    document.getElementById('preview').textContent = JSON.stringify(workflow, null, 2);
}

// Copy workflow to clipboard
async function copyToClipboard() {
    if (!workflow) {
        alert('No workflow to copy');
        return;
    }

    const json = JSON.stringify(workflow, null, 2);
    const button = document.getElementById('copyButton');
    const originalText = button.textContent;

    try {
        await navigator.clipboard.writeText(json);
        button.textContent = 'Copied!';
        button.classList.remove('bg-gray-600', 'hover:bg-gray-700');
        button.classList.add('bg-green-600', 'hover:bg-green-700');

        setTimeout(() => {
            button.textContent = originalText;
            button.classList.remove('bg-green-600', 'hover:bg-green-700');
            button.classList.add('bg-gray-600', 'hover:bg-gray-700');
        }, 2000);
    } catch (err) {
        console.error('Failed to copy:', err);
        alert('Failed to copy to clipboard');
    }
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

// Utility
function formatLabel(name) {
    return name
        .replace(/([A-Z])/g, ' $1')
        .replace(/^./, str => str.toUpperCase())
        .trim();
}

// Initialize on load
loadTypes();
