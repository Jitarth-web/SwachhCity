import os
import re

files = [
    'citizen-app/index.html',
    'crew-app/index.html',
    'admin-dashboard/index.html'
]

login_js_template = """      // Handle Login
      async function handleLogin(event) {
        event.preventDefault();
        
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        
        const loginBtn = document.getElementById('loginBtn');
        const originalText = loginBtn.textContent;
        
        loginBtn.disabled = true;
        loginBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Logging in...';

        try {
          const response = await fetch('http://localhost:8005/auth/login', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              username: username,
              password: password
            }),
          });
          
          if (response.ok) {
            const data = await response.json();
            currentUser = data.user;
            authToken = data.access_token;
            
            if (currentUser.role !== ROLE_NAME) {
                showAlert(`Access Denied: This portal is for ${ROLE_NAME}s.`, 'danger');
                return;
            }
            
            localStorage.setItem('swachhgram_token', authToken);
            localStorage.setItem('swachhgram_user', JSON.stringify(currentUser));
            
            if (typeof showMainApp === 'function') showMainApp();
            if (typeof loadDashboardData === 'function') loadDashboardData();
            
            if (typeof showAlert === 'function') showAlert('Login successful!', 'success');
            else alert('Login successful!');
          } else {
            const errorData = await response.json();
            if (typeof showAlert === 'function') showAlert(`Login failed: ${errorData.detail || 'Invalid credentials'}`, 'danger');
            else alert(`Login failed: ${errorData.detail || 'Invalid credentials'}`);
          }
        } catch (error) {
          console.error('Login error:', error);
          if (typeof showAlert === 'function') showAlert('Login failed. Please try again.', 'danger');
          else alert('Login failed. Please try again.');
        } finally {
          loginBtn.disabled = false;
          loginBtn.textContent = originalText;
        }
      }"""

for filepath in files:
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We will use regex to find the `async function handleLogin(event) { ... }` block
    # and replace it entirely.
    # To do this safely, we find `async function handleLogin(event) {` and match until the end of the function.
    # Since regex for balanced braces is hard, we can just replace everything between 
    # `async function handleLogin(event) {` and the next `function ` or `//` comment block that starts a new section.
    
    role_name = "citizen"
    if "crew-app" in filepath:
        role_name = "crew"
    elif "admin-dashboard" in filepath:
        role_name = "admin"
        
    custom_js = login_js_template.replace("ROLE_NAME", f"'{role_name}'")
    
    # Let's find the start of handleLogin
    start_idx = content.find("async function handleLogin(event) {")
    if start_idx == -1:
        print(f"Could not find handleLogin in {filepath}")
        continue
        
    # Find the end by looking for the next function definition or a specific comment
    # In citizen-app, next is `// Get current location` or `function getCurrentLocation()`
    # In crew-app, next is `// Complete collection`
    # In admin-dashboard, next is `// Load dashboard data`
    
    end_idx = content.find("      //", start_idx + 10)
    if end_idx == -1:
        end_idx = content.find("      function", start_idx + 10)
        
    if end_idx != -1:
        # replace the slice
        new_content = content[:start_idx] + custom_js + "\n\n" + content[end_idx:]
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated handleLogin in {filepath}")
    else:
        print(f"Could not find end of handleLogin in {filepath}")
