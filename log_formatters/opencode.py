#!/usr/bin/env python3
import sys
import json

# Set to control verbosity - set to False to hide all intermediate events
VERBOSE = False

for line in sys.stdin:
    try:
        d = json.loads(line)
        t = d.get('type', '')

        # Silently ignore these verbose event types
        if t in ['text', 'thinking', 'session_start', 'session_end']:
            continue

        if t == 'step_start':
            if VERBOSE:
                print('⏳ Step...', flush=True)
        elif t == 'step_finish':
            p = d.get('part', {})
            c = p.get('cost', 0)
            tokens = p.get('tokens', {})
            reasoning = tokens.get('reasoning', 0)
            output = tokens.get('output', 0)

            # Show thinking if present
            if reasoning > 0:
                print(f'💭 Thinking... ({reasoning} tokens)', flush=True)

            # Show cost and output
            if c > 0:
                print(f'✓ ${c:.3f} ({output} output)', flush=True)

        elif t == 'tool_use':
            p = d.get('part', {})
            tool = p.get('tool', '')
            st = p.get('state', {})
            inp = st.get('input', {})

            # Only show completed tool uses to reduce noise
            if st.get('status') != 'completed' and not VERBOSE:
                continue

            if tool == 'task':
                desc = inp.get('description', '')[:40]
                if st.get('status') == 'completed':
                    time_info = st.get('time', {})
                    if time_info:
                        dur = (time_info.get('end', 0) - time_info.get('start', 0)) / 1000
                        print(f'🤖 {desc} [{dur:.1f}s]', flush=True)
                    else:
                        print(f'🤖 {desc}', flush=True)
                else:
                    print(f'🤖 Starting: {desc}...', flush=True)
            elif tool == 'list':
                path = inp.get('path', '.')
                if VERBOSE:
                    print(f'📂 List {path}', flush=True)
            elif tool == 'glob':
                pattern = inp.get('pattern', '')[:30]
                if VERBOSE:
                    print(f'🔍 Search: {pattern}', flush=True)
            elif tool == 'read':
                file = inp.get('filePath', '').split('/')[-1][:30]
                if st.get('status') == 'error':
                    print(f'❌ Not found: {file}', flush=True)
                elif VERBOSE:
                    print(f'📖 Read: {file}', flush=True)
            elif tool == 'write':
                file = inp.get('filePath', '').split('/')[-1][:30]
                print(f'✏️ Write: {file}', flush=True)
            elif tool == 'todowrite':
                todos = inp.get('todos', [])
                done = len([t for t in todos if t.get('status') == 'completed'])
                active = len([t for t in todos if t.get('status') != 'completed'])
                print(f'✅ Todos: {done}/{len(todos)} done', flush=True)
            elif tool == 'bash':
                # For bash commands, check if it's an echidna command and show it
                command = inp.get('command', '')
                if 'echidna' in command:
                    # Show the full echidna command
                    print(f'🔍 ECHIDNA: {command}', flush=True)
                elif VERBOSE:
                    print(f'🔧 bash', flush=True)
            # Suppress other tools in non-verbose mode
            elif VERBOSE:
                print(f'🔧 {tool}', flush=True)
    except json.JSONDecodeError:
        # Silently ignore non-JSON lines
        pass
    except Exception as e:
        # Silently ignore other errors to avoid breaking the pipe
        pass