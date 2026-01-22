import re
import sys
import os

# Priority classification rules
HIGH_KEYWORDS = ['urgent', 'critical', 'fixme', 'bug', 'error', 'security', 'crash', 'must', 'required', 'blocker']
MEDIUM_KEYWORDS = ['important', 'should', 'consider', 'improve', 'optimize', 'refactor', 'cleanup']
LOW_KEYWORDS = ['nice', 'optional', 'maybe', 'future', 'enhancement', 'cosmetic']

def classify_priority(todo_text):
    """Classify TODO priority based on keywords in the text"""
    text_lower = todo_text.lower()
    
    # Check for high priority keywords
    for keyword in HIGH_KEYWORDS:
        if keyword in text_lower:
            return 'HIGH'
    
    # Check for medium priority keywords
    for keyword in MEDIUM_KEYWORDS:
        if keyword in text_lower:
            return 'MEDIUM'
    
    # Check for low priority keywords
    for keyword in LOW_KEYWORDS:
        if keyword in text_lower:
            return 'LOW'
    
    # Default to MEDIUM if no keywords found
    return 'MEDIUM'

def parse_todos(grep_output):
    """Parse grep output and extract TODO comments"""
    todos = []
    lines = grep_output.strip().split('\n')
    
    current_file = ''
    current_todo = ''
    line_number = 0
    
    for line in lines:
        if not line.strip():
            continue
            
        # Check if line contains filename (grep output format)
        if line.startswith('src/clis/agent/') and ':' in line:
            parts = line.split(':', 1)
            current_file = parts[0]
            line_number = int(parts[1].split('-')[0]) if '-' in parts[1] else int(parts[1].split(':')[0])
            todo_line = parts[1].split(':', 1)[1] if ':' in parts[1] else parts[1]
            
            # Extract TODO comment
            todo_match = re.search(r'TODO[:\.\-\s]*(.*)', todo_line, re.IGNORECASE)
            if todo_match:
                todo_text = todo_match.group(1).strip()
                priority = classify_priority(todo_text)
                
                todos.append({
                    'file': current_file,
                    'line': line_number,
                    'text': todo_text,
                    'priority': priority,
                    'full_line': todo_line.strip()
                })
    
    return todos

def main():
    # Read grep output from stdin
    grep_output = sys.stdin.read()
    
    if not grep_output:
        print("No TODO comments found.")
        return
    
    todos = parse_todos(grep_output)
    
    if not todos:
        print("No TODO comments found.")
        return
    
    # Sort by priority (HIGH > MEDIUM > LOW)
    priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    todos.sort(key=lambda x: (priority_order[x['priority']], x['file'], x['line']))
    
    # Display results
    print(f"Found {len(todos)} TODO comments:\n")
    
    # Show top 3 by priority
    print("Top 3 TODOs by priority:")
    print("=" * 50)
    
    for i, todo in enumerate(todos[:3], 1):
        print(f"{i}. Priority: {todo['priority']}")
        print(f"   File: {todo['file']}:{todo['line']}")
        print(f"   Text: {todo['text']}")
        print(f"   Context: {todo['full_line']}")
        print()
    
    # Show summary by priority
    print("\nSummary by priority:")
    print("=" * 50)
    priority_counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    for todo in todos:
        priority_counts[todo['priority']] += 1
    
    for priority in ['HIGH', 'MEDIUM', 'LOW']:
        print(f"{priority}: {priority_counts[priority]} TODOs")

if __name__ == '__main__':
    main()