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
    
    old_register_link = '<a href="#" id="showRegisterBtn" style="text-decoration: none;">Don\'t have an account? Register here</a>'
    new_register_btn = '<button type="button" class="btn btn-outline-primary w-100" id="showRegisterBtn">Don\'t have an account? Register here</button>'
    
    old_login_link = '<a href="#" id="showLoginBtn" style="text-decoration: none;">Already have an account? Login</a>'
    new_login_btn = '<button type="button" class="btn btn-outline-success w-100" id="showLoginBtn">Already have an account? Login</button>'
    
    content = content.replace(old_register_link, new_register_btn)
    content = content.replace(old_login_link, new_login_btn)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
print("Updated links to buttons in all portals!")
