// Simple TypeScript interface parser
// Parses type.ts and extracts interface definitions at runtime

class TypeParser {
    constructor(typeScriptCode) {
        this.code = typeScriptCode;
        this.interfaces = {};
        this.enums = {};
    }

    parse() {
        this.parseEnums();
        this.parseInterfaces();
        return {
            interfaces: this.interfaces,
            enums: this.enums
        };
    }

    parseEnums() {
        // Match: enum Name { VALUE1, VALUE2 }
        const enumRegex = /enum\s+(\w+)\s*\{([^}]+)\}/g;
        let match;

        while ((match = enumRegex.exec(this.code)) !== null) {
            const name = match[1];
            const body = match[2];

            // Remove all line comments first
            const cleanBody = body.replace(/\/\/[^\n]*/g, '');

            // Extract enum values
            const values = cleanBody
                .split(',')
                .map(v => v.trim())
                .filter(v => v && v.length > 0);

            this.enums[name] = values;
        }
    }

    parseInterfaces() {
        // Match: interface Name { ... } or interface Name extends Other { ... }
        const interfaceRegex = /interface\s+(\w+)(?:\s+extends\s+([\w,\s]+))?\s*\{([^}]+)\}/g;
        let match;

        while ((match = interfaceRegex.exec(this.code)) !== null) {
            const name = match[1];
            const extendsClause = match[2];
            const body = match[3];

            const properties = this.parseProperties(body);

            // Handle extends
            if (extendsClause) {
                const baseInterfaces = extendsClause.split(',').map(s => s.trim());
                // Merge properties from base interfaces
                baseInterfaces.forEach(baseName => {
                    if (this.interfaces[baseName]) {
                        properties.unshift(...this.interfaces[baseName]);
                    }
                });
            }

            this.interfaces[name] = properties;
        }
    }

    parseProperties(body) {
        const properties = [];
        const lines = body.split('\n');

        for (let line of lines) {
            line = line.trim();

            // Skip empty lines and comments
            if (!line || line.startsWith('//') || line.startsWith('*')) {
                continue;
            }

            // Match: propertyName: type; or propertyName?: type;
            const propMatch = line.match(/(\w+)(\?)?:\s*([^;]+)/);
            if (propMatch) {
                const name = propMatch[1];
                const optional = !!propMatch[2];
                let type = propMatch[3].trim();

                // Remove trailing comments
                type = type.split('//')[0].trim();

                properties.push({
                    name,
                    type,
                    optional
                });
            }
        }

        return properties;
    }

    // Get field type information
    getFieldInfo(typeName) {
        // Remove any whitespace
        typeName = typeName.trim();

        // Check if it's an enum
        if (this.enums[typeName]) {
            return {
                kind: 'enum',
                values: this.enums[typeName]
            };
        }

        // Check if it's an interface
        if (this.interfaces[typeName]) {
            return {
                kind: 'interface',
                properties: this.interfaces[typeName]
            };
        }

        // Check primitive types
        if (['string', 'number', 'boolean'].includes(typeName)) {
            return {
                kind: 'primitive',
                type: typeName
            };
        }

        // Check for array types
        if (typeName.endsWith('[]')) {
            const elementType = typeName.slice(0, -2);
            return {
                kind: 'array',
                elementType: elementType
            };
        }

        // Check for union types (e.g., 'task' | 'decision')
        if (typeName.includes('|')) {
            const types = typeName.split('|').map(t => t.trim().replace(/['"]/g, ''));
            return {
                kind: 'union',
                types: types
            };
        }

        return {
            kind: 'unknown',
            type: typeName
        };
    }
}

// Form generator from parsed types
class FormGenerator {
    constructor(parsedTypes) {
        this.types = parsedTypes;
        this.parser = new TypeParser('');
        this.parser.interfaces = parsedTypes.interfaces;
        this.parser.enums = parsedTypes.enums;
    }

    // Generate HTML input for a field
    generateField(property, path, currentValue) {
        const { name, type, optional } = property;
        const fieldInfo = this.parser.getFieldInfo(type);
        const value = currentValue || '';
        const fullPath = path ? `${path}.${name}` : name;

        switch (fieldInfo.kind) {
            case 'primitive':
                if (type === 'boolean') {
                    return `
                        <label class="flex items-center gap-2 text-sm">
                            <input
                                type="checkbox"
                                data-path="${fullPath}"
                                ${value ? 'checked' : ''}
                                onchange="updateWorkflowField('${fullPath}', this.checked)"
                            />
                            ${this.formatLabel(name)}
                        </label>
                    `;
                } else if (type === 'number') {
                    return `
                        <div>
                            <label class="block text-sm font-medium mb-1">${this.formatLabel(name)}</label>
                            <input
                                type="number"
                                data-path="${fullPath}"
                                value="${value}"
                                class="w-full px-3 py-2 border rounded text-sm"
                                oninput="updateWorkflowField('${fullPath}', parseFloat(this.value))"
                            />
                        </div>
                    `;
                } else {
                    return `
                        <div>
                            <label class="block text-sm font-medium mb-1">${this.formatLabel(name)}</label>
                            <input
                                type="text"
                                data-path="${fullPath}"
                                value="${value}"
                                placeholder="${optional ? '(optional)' : ''}"
                                class="w-full px-3 py-2 border rounded text-sm"
                                oninput="updateWorkflowField('${fullPath}', this.value)"
                            />
                        </div>
                    `;
                }

            case 'enum':
                return `
                    <div>
                        <label class="block text-sm font-medium mb-1">${this.formatLabel(name)}</label>
                        <select
                            data-path="${fullPath}"
                            class="w-full px-3 py-2 border rounded text-sm"
                            onchange="updateWorkflowField('${fullPath}', this.value)"
                        >
                            ${fieldInfo.values.map(v => `
                                <option value="${v}" ${value === v ? 'selected' : ''}>${v}</option>
                            `).join('')}
                        </select>
                    </div>
                `;

            case 'union':
                return `
                    <div>
                        <label class="block text-sm font-medium mb-1">${this.formatLabel(name)}</label>
                        <select
                            data-path="${fullPath}"
                            class="w-full px-3 py-2 border rounded text-sm"
                            onchange="updateWorkflowField('${fullPath}', this.value)"
                        >
                            ${fieldInfo.types.map(t => `
                                <option value="${t}" ${value === t ? 'selected' : ''}>${t}</option>
                            `).join('')}
                        </select>
                    </div>
                `;

            case 'interface':
                return `
                    <div class="border-l-2 border-gray-300 pl-4">
                        <h4 class="text-sm font-medium mb-2">${this.formatLabel(name)}</h4>
                        ${fieldInfo.properties.map(prop =>
                            this.generateField(prop, fullPath, currentValue?.[name]?.[prop.name])
                        ).join('')}
                    </div>
                `;

            default:
                return `
                    <div>
                        <label class="block text-sm font-medium mb-1">${this.formatLabel(name)} (${type})</label>
                        <textarea
                            data-path="${fullPath}"
                            class="w-full px-3 py-2 border rounded text-sm"
                            oninput="updateWorkflowField('${fullPath}', this.value)"
                        >${value}</textarea>
                    </div>
                `;
        }
    }

    formatLabel(name) {
        return name
            .replace(/([A-Z])/g, ' $1')
            .replace(/^./, str => str.toUpperCase())
            .trim();
    }
}
