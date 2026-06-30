import os
import re

admin_html = 'c:/Users/jitar/OneDrive/Desktop/swachhgram/admin-dashboard/index.html'

if os.path.exists(admin_html):
    with open(admin_html, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add mobile toggle button
    nav_pattern = r'(<nav class="navbar navbar-expand-lg navbar-dark">\s*<div class="container-fluid">\s*<a class="navbar-brand"[^>]*>.*?</a>)'
    
    if '<button class="navbar-toggler"' not in content:
        replacement = r'\1\n          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#adminNavbar">\n            <span class="navbar-toggler-icon"></span>\n          </button>\n          <div class="collapse navbar-collapse" id="adminNavbar">'
        content = re.sub(nav_pattern, replacement, content, flags=re.DOTALL)
        
        # Close the div after the navbar-nav
        nav_end_pattern = r'(<div class="navbar-nav ms-auto">.*?</div>)'
        content = re.sub(nav_end_pattern, r'\1\n          </div>', content, flags=re.DOTALL)
        
    # Also adjust columns for responsive metrics cards
    content = content.replace('col-md-3 mb-3', 'col-sm-6 col-md-3 mb-3')
    content = content.replace('col-md-8', 'col-lg-8 col-md-12 mb-4')
    content = content.replace('col-md-4', 'col-lg-4 col-md-12')
    
    # Back to Main Website responsive margin
    content = content.replace('<a href="http://localhost:3000/" class="text-muted"', '<a href="../index.html" class="text-muted"')
    
    with open(admin_html, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Admin dashboard responsive updates complete.")
else:
    print("Admin dashboard HTML not found.")
