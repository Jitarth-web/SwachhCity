import re
import os

files_to_update = [
    'citizen-app/index.html',
    'crew-app/index.html',
    'admin-dashboard/index.html'
]

html_replacement = """    <!-- Login/Register Screen -->
    <div id="loginScreen" class="login-container">
      <div class="login-card">
        <div class="text-center mb-4">
          <h2>SwachhCity</h2>
          <p class="text-muted">PORTAL_NAME</p>
        </div>
        
        <!-- Flash Message Container -->
        <div id="flashMessage" class="alert alert-success" style="display: none; position: static; margin-bottom: 20px;"></div>
        
        <form id="loginForm">
          <div class="mb-3">
            <label for="username" class="form-label">Username</label>
            <input type="text" class="form-control" id="username" placeholder="Enter username" required>
          </div>
          
          <div class="mb-3">
            <label for="password" class="form-label">Password</label>
            <input type="password" class="form-control" id="password" placeholder="Enter password" required>
          </div>
          
          <button type="submit" class="btn btn-primary w-100" id="loginBtn">
            <span id="loginBtnText">Login</span>
          </button>
          
          <div class="text-center mt-3">
            <a href="#" id="showRegisterBtn" style="text-decoration: none;">Don't have an account? Register here</a>
          </div>
        </form>

        <form id="registerForm" style="display: none;">
          <div class="mb-3">
            <label for="regName" class="form-label">Full Name</label>
            <input type="text" class="form-control" id="regName" placeholder="Enter full name" required>
          </div>
          <div class="mb-3">
            <label for="regUsername" class="form-label">Username</label>
            <input type="text" class="form-control" id="regUsername" placeholder="Choose a username" required>
          </div>
          <div class="mb-3">
            <label for="regPassword" class="form-label">Password</label>
            <input type="password" class="form-control" id="regPassword" placeholder="Create a password" required>
          </div>
          <button type="submit" class="btn btn-success w-100" id="registerBtn">
            <span id="registerBtnText">Register</span>
          </button>
          <div class="text-center mt-3">
            <a href="#" id="showLoginBtn" style="text-decoration: none;">Already have an account? Login</a>
          </div>
        </form>
      </div>
    </div>

    <!-- Main App -->"""

js_replacement = """
      // Handle Registration
      async function handleRegister(e) {
        e.preventDefault();
        
        const name = document.getElementById('regName').value;
        const username = document.getElementById('regUsername').value;
        const password = document.getElementById('regPassword').value;
        const btn = document.getElementById('registerBtn');
        const btnText = document.getElementById('registerBtnText');
        const flashMsg = document.getElementById('flashMessage');
        
        // Disable button and show loading
        btn.disabled = true;
        btnText.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Registering...';
        
        try {
          const response = await fetch(`${AUTH_API_URL}/auth/register`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              name: name,
              username: username,
              password: password,
              role: ROLE_NAME
            }),
          });
          
          const data = await response.json();
          
          if (response.ok) {
            // Show flash message
            flashMsg.className = "alert alert-success";
            flashMsg.innerHTML = `<strong>Success!</strong> You can now login.<br>ID: ${username}<br>Password: ${password}`;
            flashMsg.style.display = "block";
            
            // Switch back to login form
            document.getElementById('registerForm').style.display = 'none';
            document.getElementById('loginForm').style.display = 'block';
            
            // Pre-fill login form
            document.getElementById('username').value = username;
            document.getElementById('password').value = password;
          } else {
            alert(`Registration failed: ${data.detail || 'Unknown error'}`);
          }
        } catch (error) {
          console.error('Registration error:', error);
          alert('Failed to connect to authentication server. Please ensure it is running.');
        } finally {
          // Re-enable button
          btn.disabled = false;
          btnText.innerText = 'Register';
        }
      }

      // Handle Login
      async function handleLogin(e) {"""

init_replacement = """
        document.getElementById('loginForm').addEventListener('submit', handleLogin);
        document.getElementById('registerForm').addEventListener('submit', handleRegister);
        
        document.getElementById('showRegisterBtn').addEventListener('click', (e) => {
          e.preventDefault();
          document.getElementById('loginForm').style.display = 'none';
          document.getElementById('registerForm').style.display = 'block';
          document.getElementById('flashMessage').style.display = 'none';
        });
        
        document.getElementById('showLoginBtn').addEventListener('click', (e) => {
          e.preventDefault();
          document.getElementById('registerForm').style.display = 'none';
          document.getElementById('loginForm').style.display = 'block';
        });
"""

for filepath in files_to_update:
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Determine portal name and role
    portal_name = "Citizen Portal"
    role_name = "citizen"
    if "crew-app" in filepath:
        portal_name = "Crew Portal"
        role_name = "crew"
    elif "admin-dashboard" in filepath:
        portal_name = "Admin Dashboard"
        role_name = "admin"
        
    # 2. Replace HTML
    # We use regex to find everything between <!-- Login Screen --> and <!-- Main App -->
    pattern_html = re.compile(r'<!-- Login Screen -->.*?<!-- Main App -->', re.DOTALL)
    
    custom_html = html_replacement.replace("PORTAL_NAME", portal_name)
    content = pattern_html.sub(custom_html, content)
    
    # 3. Replace JS handleLogin to include handleRegister
    custom_js = js_replacement.replace("ROLE_NAME", f"'{role_name}'")
    content = content.replace("async function handleLogin(e) {", custom_js)
    
    # 4. Add event listeners
    content = content.replace("document.getElementById('loginForm').addEventListener('submit', handleLogin);", init_replacement)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print("Updated all portals with registration flow!")
