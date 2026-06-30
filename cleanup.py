import os

# 1. Clean up garbage JS
files = [
    'citizen-app/index.html',
    'crew-app/index.html',
    'admin-dashboard/index.html'
]

for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We will search for the garbage starting at "// For demo, we'll use simple authentication"
    # and delete it up to the next valid function definition.
    start_garbage = content.find("      // For demo, we'll use simple authentication")
    if start_garbage != -1:
        end_garbage = content.find("      //", start_garbage + 10)
        if end_garbage == -1:
            end_garbage = content.find("      function", start_garbage + 10)
            
        if end_garbage != -1:
            content = content[:start_garbage] + content[end_garbage:]
            
    # Fix the Register button colors
    if "citizen-app" in filepath:
        pass # Already btn-success (green)
    elif "crew-app" in filepath:
        # Change Register button to purple
        content = content.replace('class="btn btn-success w-100" id="registerBtn"', 'class="btn w-100" style="background-color: #6366f1; color: white;" id="registerBtn"')
    elif "admin-dashboard" in filepath:
        # Change Register button and background
        # Admin background currently is linear-gradient(135deg, #1e293b, #0f172a)
        content = content.replace('background: linear-gradient(135deg, #2e7d32, #388e3c);', 'background: linear-gradient(135deg, #475569, #1e293b);')
        # Wait, the login-container background in admin might already be different. Let's force it.
        
        # Change Register button to match background
        content = content.replace('class="btn btn-success w-100" id="registerBtn"', 'class="btn btn-dark w-100" id="registerBtn"')
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
print("Cleaned up JS and updated button colors!")
