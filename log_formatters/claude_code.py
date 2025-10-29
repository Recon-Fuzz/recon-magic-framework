import sys, json
for line in sys.stdin:
    try:
        data = json.loads(line)
        if data.get('type') == 'assistant' and data.get('message', {}).get('content'):
            for item in data['message']['content']:
                if item.get('type') == 'text':
                    print('💭 ' + item['text'])
                elif item.get('type') == 'tool_use':
                    tool_name = item.get('name', 'unknown')
                    if 'input' in item and 'command' in item['input']:
                        print(f'⚡ [{tool_name}] ' + item['input']['command'])
                    else:
                        print(f'⚡ [{tool_name}]')
        elif data.get('type') == 'user' and data.get('message', {}).get('content'):
            for item in data['message']['content']:
                if item.get('type') == 'tool_result' and item.get('is_error'):
                    tool_name = item.get('tool_use', {}).get('name', 'unknown')
                    print(f'❌ [{tool_name}] ' + item['content'].split('\n')[0])
    except: pass