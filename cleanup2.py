import os

files = [
    'citizen-app/index.html',
    'crew-app/index.html',
    'admin-dashboard/index.html'
]

for filepath in files:
    if not os.path.exists(filepath):
        continue
    
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

    # Button fixes
    if "citizen-app" in filepath:
        # Green is btn-success. Ensure it's set.
        pass 
    elif "crew-app" in filepath:
        # Crew: Purple
        content = content.replace('class="btn btn-success w-100" id="registerBtn"', 'class="btn w-100" style="background-color: #6366f1; color: white;" id="registerBtn"')
    elif "admin-dashboard" in filepath:
        # Admin: Change background to a dark slate
        content = content.replace('background: linear-gradient(135deg, #6366f1, #8b5cf6);', 'background: linear-gradient(135deg, #1e293b, #0f172a);')
        # Admin: Change register button to match (dark)
        content = content.replace('class="btn btn-success w-100" id="registerBtn"', 'class="btn btn-dark w-100" id="registerBtn"')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print("Cleanup complete!")
