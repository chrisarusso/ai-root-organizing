#!/usr/bin/env python3
"""
Export Claude Code conversation to markdown when session ends.
Triggered by SessionEnd hook.
"""
import json
import sys
import os
from datetime import datetime

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    transcript_path = input_data.get('transcript_path', '')
    session_id = input_data.get('session_id', '')

    if not transcript_path or not os.path.exists(transcript_path):
        sys.exit(0)

    try:
        # Read JSONL transcript
        messages = []
        with open(transcript_path, 'r') as f:
            for line in f:
                if line.strip():
                    messages.append(json.loads(line))

        if not messages:
            sys.exit(0)

        # Generate markdown filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_dir = os.environ.get('CLAUDE_PROJECT_DIR', '.')
        markdown_dir = os.path.join(project_dir, '.claude', 'transcripts')
        os.makedirs(markdown_dir, exist_ok=True)

        output_file = os.path.join(markdown_dir, f'session_{timestamp}.md')

        # Convert to markdown
        with open(output_file, 'w') as f:
            f.write(f"# Claude Code Session\n\n")
            f.write(f"- **Session ID:** {session_id}\n")
            f.write(f"- **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")

            for msg in messages:
                msg_type = msg.get('type', 'unknown')

                # Skip non-message types (like file-history-snapshot)
                if msg_type not in ('user', 'assistant'):
                    continue

                # Get the actual message content from the nested 'message' field
                message_data = msg.get('message', {})
                content = extract_content(message_data)

                # Skip empty messages (like thinking-only blocks)
                if not content.strip():
                    continue

                if msg_type == 'user':
                    f.write(f"## User\n\n{content}\n\n")
                elif msg_type == 'assistant':
                    f.write(f"## Assistant\n\n{content}\n\n")

        print(f"Session exported to {output_file}")

    except Exception as e:
        print(f"Error exporting session: {e}", file=sys.stderr)
        sys.exit(1)


def extract_content(msg):
    """Extract text content from various message formats."""
    content = msg.get('content', '')

    # Handle list of content blocks (Claude's format)
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                block_type = block.get('type', '')
                if block_type == 'text':
                    parts.append(block.get('text', ''))
                elif block_type == 'tool_use':
                    tool_name = block.get('name', 'unknown')
                    tool_input = block.get('input', {})
                    # Format tool calls nicely
                    if tool_name == 'Read':
                        file_path = tool_input.get('file_path', '')
                        parts.append(f"*[Reading: {file_path}]*")
                    elif tool_name == 'Bash':
                        cmd = tool_input.get('command', '')[:100]
                        parts.append(f"*[Running: `{cmd}`]*")
                    elif tool_name == 'Edit':
                        file_path = tool_input.get('file_path', '')
                        parts.append(f"*[Editing: {file_path}]*")
                    elif tool_name == 'Write':
                        file_path = tool_input.get('file_path', '')
                        parts.append(f"*[Writing: {file_path}]*")
                    elif tool_name == 'Glob' or tool_name == 'Grep':
                        pattern = tool_input.get('pattern', '')
                        parts.append(f"*[{tool_name}: {pattern}]*")
                    else:
                        parts.append(f"*[Tool: {tool_name}]*")
                elif block_type == 'tool_result':
                    # Include truncated tool results
                    result = block.get('content', '')
                    if isinstance(result, str) and len(result) > 500:
                        result = result[:500] + "... (truncated)"
                    if result:
                        parts.append(f"```\n{result}\n```")
                # Skip 'thinking' blocks - they're internal reasoning
            elif isinstance(block, str):
                parts.append(block)
        return '\n'.join(filter(None, parts))

    return str(content) if content else ''


if __name__ == '__main__':
    main()
