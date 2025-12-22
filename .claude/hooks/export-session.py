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

                if msg_type == 'user':
                    content = extract_content(msg)
                    f.write(f"## User\n\n{content}\n\n")
                elif msg_type == 'assistant':
                    content = extract_content(msg)
                    f.write(f"## Assistant\n\n{content}\n\n")
                elif msg_type == 'tool_use':
                    tool_name = msg.get('name', msg.get('tool_name', 'unknown'))
                    tool_input = msg.get('input', msg.get('tool_input', {}))
                    f.write(f"### Tool: {tool_name}\n\n")
                    f.write(f"```json\n{json.dumps(tool_input, indent=2)}\n```\n\n")
                elif msg_type == 'tool_result':
                    content = extract_content(msg)
                    # Truncate long tool results
                    if len(content) > 2000:
                        content = content[:2000] + "\n... (truncated)"
                    f.write(f"### Result\n\n```\n{content}\n```\n\n")

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
                if block.get('type') == 'text':
                    parts.append(block.get('text', ''))
                elif block.get('type') == 'tool_use':
                    parts.append(f"[Tool: {block.get('name', 'unknown')}]")
            elif isinstance(block, str):
                parts.append(block)
        return '\n'.join(parts)

    return str(content)


if __name__ == '__main__':
    main()
