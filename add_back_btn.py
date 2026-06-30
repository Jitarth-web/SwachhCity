import os

files = [
    'citizen-app/index.html',
    'crew-app/index.html',
    'admin-dashboard/index.html'
]

back_button_html = """        </form>
        <div class="text-center mt-4 border-top pt-3">
          <a href="http://localhost:3000/" class="text-muted" style="text-decoration: none; font-size: 0.9rem; transition: color 0.2s;" onmouseover="this.style.color='#000'" onmouseout="this.style.color=''">
            ← Back to Main Website
          </a>
        </div>
      </div>"""

for filepath in files:
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We find the end of the register form inside the login card
    target = "        </form>\n      </div>"
    if target in content:
        content = content.replace(target, back_button_html)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Added back button to {filepath}")
    else:
        print(f"Target not found in {filepath}")
