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

        // Debug: Check DecisionStepReadFileWithDigest
        const digestInterface = parsedTypes.interfaces['DecisionStepReadFileWithDigest'];
        console.log('🔍 DecisionStepReadFileWithDigest:', digestInterface);
        if (digestInterface) {
            const modeInfoProp = digestInterface.find(p => p.name === 'modeInfo');
            console.log('🔍 modeInfo property:', modeInfoProp);
        }

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

// Add new step - auto-generated from types
function addStep(type) {
    // Get default values from parsed types
    const defaultModelType = parsedTypes.enums['ModelType']?.[0] || 'INHERIT';
    const defaultDecisionMode = parsedTypes.enums['DecisionMode']?.[0] || 'FILE_EXISTS';

    // Get default operator and action from Decision interface
    const decisionProps = parsedTypes.interfaces['Decision'] || [];
    const operatorProp = decisionProps.find(p => p.name === 'operator');
    const actionProp = decisionProps.find(p => p.name === 'action');
    const operatorInfo = operatorProp ? formGenerator.parser.getFieldInfo(operatorProp.type) : null;
    const actionInfo = actionProp ? formGenerator.parser.getFieldInfo(actionProp.type) : null;
    const defaultOperator = operatorInfo?.types?.[0] || 'eq';
    const defaultAction = actionInfo?.types?.[0] || 'CONTINUE';

    let stepTemplate;

    if (type === 'task') {
        stepTemplate = {
            type: 'task',
            name: `Step ${workflow.steps.length + 1}`,
            description: '',
            prompt: '',
            model: {
                type: defaultModelType,
                model: 'inherit'
            },
            shouldCreateSummary: false,
            shouldCommitChanges: true
        };
    } else {
        // Build modeInfo dynamically from schema
        const modeInfoFields = getModeInfoSchema(defaultDecisionMode);
        const modeInfo = {};
        modeInfoFields.forEach(field => {
            modeInfo[field.name] = '';
        });

        stepTemplate = {
            type: 'decision',
            name: `Decision ${workflow.steps.length + 1}`,
            description: '',
            mode: defaultDecisionMode,
            modeInfo: modeInfo,
            decision: [
                { operator: defaultOperator, value: 0, action: defaultAction }
            ],
            shouldCreateSummary: false,
            shouldCommitChanges: false
        };

        // Only add model if this mode needs it
        if (modeNeedsModel(defaultDecisionMode)) {
            stepTemplate.model = {
                type: defaultModelType,
                model: 'inherit'
            };
        }
    }

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

// Check if a decision mode needs a model field
function modeNeedsModel(mode) {
    // Get the interface for this mode
    const decisionInterfaces = Object.keys(parsedTypes.interfaces).filter(name =>
        name.startsWith('DecisionStep') && name !== 'DecisionStep'
    );

    for (const interfaceName of decisionInterfaces) {
        const interfaceProps = parsedTypes.interfaces[interfaceName];
        const modeProp = interfaceProps.find(p => p.name === 'mode');

        if (modeProp && modeProp.type.includes(mode)) {
            // Check if this interface has a model property
            return interfaceProps.some(p => p.name === 'model');
        }
    }

    return false;
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
    // For decision steps, also skip 'model' if the mode doesn't need it
    let skipFields = ['type', 'decision', 'mode', 'modeInfo'];
    if (step.type === 'decision' && !modeNeedsModel(step.mode)) {
        skipFields.push('model');
    }

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
    const fieldInfo = formGenerator.parser.getFieldInfo(prop.type, prop);

    switch (fieldInfo.kind) {
        case 'inline_object':
            // Render inline object (like modeInfo)
            const inlineProps = fieldInfo.properties;
            return `
                <div class="border-l-2 border-green-300 pl-3">
                    <h5 class="text-xs font-semibold text-gray-600 mb-2">${formatLabel(prop.name)}</h5>
                    ${inlineProps.map(inlineProp => {
                        const inlineValue = currentValue?.[inlineProp.name];
                        return generateNestedFieldHtml(inlineProp, stepIndex, prop.name, inlineValue);
                    }).join('')}
                </div>
            `;

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

// Get modeInfo schema for a specific decision mode from parsed types
function getModeInfoSchema(mode) {
    // Search through all interfaces that extend DecisionBase to find the one with this mode
    const decisionInterfaces = Object.keys(parsedTypes.interfaces).filter(name =>
        name.startsWith('DecisionStep') && name !== 'DecisionStep'
    );

    console.log(`Looking for mode "${mode}" in interfaces:`, decisionInterfaces);

    for (const interfaceName of decisionInterfaces) {
        const interfaceProps = parsedTypes.interfaces[interfaceName];

        // Find the mode property
        const modeProp = interfaceProps.find(p => p.name === 'mode');

        console.log(`  ${interfaceName}: mode prop =`, modeProp?.type);

        // Check if this interface's mode matches (format: "DecisionMode.FILE_EXISTS")
        if (modeProp && modeProp.type.includes(mode)) {
            console.log(`  ✓ Found matching interface: ${interfaceName}`);

            // Find the modeInfo property in this interface
            const modeInfoProp = interfaceProps.find(p => p.name === 'modeInfo');

            console.log(`  modeInfo prop:`, modeInfoProp);

            if (modeInfoProp) {
                // Get the properties of the inline object
                const fieldInfo = formGenerator.parser.getFieldInfo(modeInfoProp.type, modeInfoProp);

                console.log(`  fieldInfo:`, fieldInfo);

                if (fieldInfo.kind === 'inline_object') {
                    console.log(`  ✓ Returning ${fieldInfo.properties.length} properties`);
                    return fieldInfo.properties;
                }
            }
        }
    }

    console.log(`  ✗ No matching interface found for mode "${mode}"`);
    return [];
}

// Render decision mode and modeInfo fields dynamically from types
function renderDecisionModeFields(step, stepIndex) {
    // Get DecisionMode enum values from parsed types
    const modes = parsedTypes.enums['DecisionMode'] || [];

    // Get modeInfo schema for current mode
    const modeInfoFields = getModeInfoSchema(step.mode);
    console.log(`Mode: ${step.mode}, Found ${modeInfoFields.length} modeInfo fields:`, modeInfoFields);

    return `
        <div>
            <label class="block text-sm font-medium mb-1">Decision Mode</label>
            <select
                class="w-full px-3 py-2 border rounded text-sm"
                onchange="handleModeChange(${stepIndex}, this.value)"
            >
                ${modes.map(m => `
                    <option value="${m}" ${step.mode === m ? 'selected' : ''}>${m}</option>
                `).join('')}
            </select>
        </div>
        <div class="border-l-2 border-purple-300 pl-3 space-y-2">
            <h5 class="text-xs font-semibold text-gray-600">Mode Info</h5>
            ${modeInfoFields.length === 0 ? '<p class="text-xs text-gray-500">No fields for this mode</p>' : ''}
            ${modeInfoFields.map(field => {
                const value = step.modeInfo?.[field.name] || '';
                const isPrompt = field.name === 'prompt';

                return `
                    <div>
                        <label class="block text-sm font-medium mb-1">${formatLabel(field.name)}</label>
                        ${isPrompt ? `
                            <textarea
                                class="w-full px-3 py-2 border rounded text-sm h-24"
                                placeholder="${field.name === 'prompt' ? 'Instructions for the LLM to make a decision...' : ''}"
                                oninput="updateModeInfoField(${stepIndex}, '${field.name}', this.value)"
                            >${value}</textarea>
                        ` : `
                            <input
                                type="text"
                                value="${value}"
                                placeholder="e.g., skip.txt or results.md"
                                class="w-full px-3 py-2 border rounded text-sm"
                                oninput="updateModeInfoField(${stepIndex}, '${field.name}', this.value)"
                            />
                        `}
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

// Render decision rules (array handling)
function renderDecisionRules(step, stepIndex) {
    if (!step.decision) return '';

    // Get list of available step names for JUMP_TO_STEP
    const stepNames = workflow.steps.map(s => s.name);

    // Get action values from Decision interface's action property
    const decisionProps = parsedTypes.interfaces['Decision'] || [];
    const actionProp = decisionProps.find(p => p.name === 'action');
    const actionInfo = actionProp ? formGenerator.parser.getFieldInfo(actionProp.type) : null;
    const actions = actionInfo && actionInfo.kind === 'union' ? actionInfo.types : [];

    // Get operator values from Decision interface's operator property
    const operatorProp = decisionProps.find(p => p.name === 'operator');
    const operatorInfo = operatorProp ? formGenerator.parser.getFieldInfo(operatorProp.type) : null;
    const operators = operatorInfo && operatorInfo.kind === 'union' ? operatorInfo.types : [];

    // Operator display names
    const operatorLabels = {
        'eq': '=',
        'neq': '!=',
        'gt': '>',
        'lt': '<',
        'gte': '≥',
        'lte': '≤'
    };

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
                <div class="border p-2 rounded mb-2 space-y-2">
                    <div class="flex gap-2 items-center">
                        <select
                            class="px-2 py-1 border rounded text-xs"
                            onchange="updateDecisionRule(${stepIndex}, ${ruleIndex}, 'operator', this.value)"
                        >
                            ${operators.map(op => `
                                <option value="${op}" ${rule.operator === op ? 'selected' : ''}>${operatorLabels[op] || op}</option>
                            `).join('')}
                        </select>
                        <input
                            type="number"
                            value="${rule.value}"
                            class="px-2 py-1 border rounded text-xs w-20"
                            oninput="updateDecisionRule(${stepIndex}, ${ruleIndex}, 'value', parseFloat(this.value))"
                        />
                        <select
                            class="px-2 py-1 border rounded text-xs flex-1"
                            onchange="handleActionChange(${stepIndex}, ${ruleIndex}, this.value)"
                        >
                            ${actions.map(action => `
                                <option value="${action}" ${rule.action === action ? 'selected' : ''}>${formatActionLabel(action)}</option>
                            `).join('')}
                        </select>
                        <button
                            onclick="removeDecisionRule(${stepIndex}, ${ruleIndex})"
                            class="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700"
                        >✕</button>
                    </div>
                    ${rule.action === 'JUMP_TO_STEP' ? `
                        <div>
                            <label class="block text-xs font-medium mb-1">Destination Step</label>
                            <select
                                class="w-full px-2 py-1 border rounded text-xs"
                                onchange="updateDecisionRule(${stepIndex}, ${ruleIndex}, 'destinationStep', this.value)"
                            >
                                <option value="">-- Select Step --</option>
                                ${stepNames.map(name => `
                                    <option value="${name}" ${rule.destinationStep === name ? 'selected' : ''}>${name}</option>
                                `).join('')}
                            </select>
                        </div>
                    ` : ''}
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

function updateModeInfoField(stepIndex, fieldName, value) {
    if (!workflow.steps[stepIndex].modeInfo) {
        workflow.steps[stepIndex].modeInfo = {};
    }
    workflow.steps[stepIndex].modeInfo[fieldName] = value;
    updatePreview();
}

function handleModeChange(stepIndex, newMode) {
    workflow.steps[stepIndex].mode = newMode;

    // Reset modeInfo dynamically based on the schema for this mode
    const modeInfoFields = getModeInfoSchema(newMode);

    workflow.steps[stepIndex].modeInfo = {};

    // Initialize all fields from the schema with empty values
    modeInfoFields.forEach(field => {
        workflow.steps[stepIndex].modeInfo[field.name] = '';
    });

    // Re-render to show/hide appropriate fields
    renderSteps();
    updatePreview();
}

function updateDecisionRule(stepIndex, ruleIndex, field, value) {
    workflow.steps[stepIndex].decision[ruleIndex][field] = value;
    updatePreview();
}

function handleActionChange(stepIndex, ruleIndex, action) {
    workflow.steps[stepIndex].decision[ruleIndex].action = action;

    // Clear destinationStep if not JUMP_TO_STEP
    if (action !== 'JUMP_TO_STEP') {
        delete workflow.steps[stepIndex].decision[ruleIndex].destinationStep;
    }

    // Re-render to show/hide destination field
    renderSteps();
    updatePreview();
}

function addDecisionRule(stepIndex) {
    if (!workflow.steps[stepIndex].decision) {
        workflow.steps[stepIndex].decision = [];
    }

    // Get default operator and action from Decision interface
    const decisionProps = parsedTypes.interfaces['Decision'] || [];
    const operatorProp = decisionProps.find(p => p.name === 'operator');
    const actionProp = decisionProps.find(p => p.name === 'action');
    const operatorInfo = operatorProp ? formGenerator.parser.getFieldInfo(operatorProp.type) : null;
    const actionInfo = actionProp ? formGenerator.parser.getFieldInfo(actionProp.type) : null;
    const defaultOperator = operatorInfo?.types?.[0] || 'eq';
    const defaultAction = actionInfo?.types?.[0] || 'CONTINUE';

    workflow.steps[stepIndex].decision.push({
        operator: defaultOperator,
        value: 0,
        action: defaultAction
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

function formatActionLabel(action) {
    // Convert SCREAMING_SNAKE_CASE to Title Case
    return action
        .split('_')
        .map(word => word.charAt(0) + word.slice(1).toLowerCase())
        .join(' ');
}

// Initialize on load
loadTypes();
