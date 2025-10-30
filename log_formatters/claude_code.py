import sys, json

for line in sys.stdin:
    try:
        data = json.loads(line)

        # Skip noisy init and system messages
        if data.get('type') in ['system', 'init']:
            continue

        if data.get('type') == 'assistant' and data.get('message', {}).get('content'):
            for item in data['message']['content']:
                if item.get('type') == 'text':
                    print('💭 ' + item['text'])
                elif item.get('type') == 'tool_use':
                    tool_name = item.get('name', 'unknown')
                    if 'input' in item and 'command' in item['input']:
                        print(f'⚡ [{tool_name}] {item["input"]["command"]}')
                    elif 'input' in item and 'description' in item['input']:
                        print(f'⚡ [{tool_name}] {item["input"]["description"]}')
                    else:
                        print(f'⚡ [{tool_name}]')

        elif data.get('type') == 'user' and data.get('message', {}).get('content'):
            for item in data['message']['content']:
                if item.get('type') == 'tool_result':
                    if item.get('is_error'):
                        print(f'❌ [{item.get("tool_use_id", "unknown")}] {item.get("content", "").split(chr(10))[0]}')
                    # Optionally show successful tool results (commented out to reduce noise)
                    # else:
                    #     print(f'✓ [{item.get("tool_use_id", "unknown")}]')
    except json.JSONDecodeError:
        # Not JSON, ignore
        pass
    except Exception:
        # Other errors, ignore
        pass