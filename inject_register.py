import os

files = [
    'citizen-app/index.html',
    'crew-app/index.html',
    'admin-dashboard/index.html'
]

register_js_template = """      // Handle Registration
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
          const response = await fetch('http://localhost:8005/auth/register', {
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
      async function handleLogin(event) {"""

for filepath in files:
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if handleRegister is already injected to avoid duplicates
    if "async function handleRegister" in content:
        print(f"Skipping {filepath} - already has handleRegister")
        continue

    role_name = "citizen"
    if "crew-app" in filepath:
        role_name = "crew"
    elif "admin-dashboard" in filepath:
        role_name = "admin"
        
    custom_js = register_js_template.replace("ROLE_NAME", f"'{role_name}'")
    
    # Replace the target
    content = content.replace("async function handleLogin(event) {", custom_js)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print("Injected handleRegister into portals!")
