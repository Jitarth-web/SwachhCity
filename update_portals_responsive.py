import os
import re

html_files = [
    'c:/Users/jitar/OneDrive/Desktop/swachhgram/citizen-app/index.html',
    'c:/Users/jitar/OneDrive/Desktop/swachhgram/crew-app/index.html',
    'c:/Users/jitar/OneDrive/Desktop/swachhgram/admin-dashboard/index.html'
]

# 1. Create config.js
config_path = 'c:/Users/jitar/OneDrive/Desktop/swachhgram/config.js'
config_content = """// SwachhGram Global Configuration
const SERVICES = {
  AUTH: 'http://localhost:8005/auth',
  SHARED_DATA: 'http://localhost:8006'
};
"""
with open(config_path, 'w', encoding='utf-8') as f:
    f.write(config_content)
print(f"Created {config_path}")

# 2. Update HTML files
for filepath in html_files:
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        continue
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add viewport meta tag if missing
    if '<meta name="viewport"' not in content:
        content = content.replace('<meta charset="UTF-8">', '<meta charset="UTF-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
    
    # Remove old SERVICES block and inject config.js
    services_pattern = r"const\s+SERVICES\s*=\s*\{[^}]+\};"
    
    # Only replace if we haven't already injected config.js
    if 'src="../config.js"' not in content:
        # First, add the script tag to the head
        head_end = content.find('</head>')
        if head_end != -1:
            content = content[:head_end] + '    <script src="../config.js"></script>\n  ' + content[head_end:]
        
        # Then, remove the inline SERVICES declaration
        content = re.sub(services_pattern, "// SERVICES configuration moved to config.js", content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print(f"Updated {filepath}")
