from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import os
import json
import requests
from datetime import datetime

app = FastAPI()

# GitHub API configuration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_API_URL = "https://api.github.com"

@app.post('/receiver')
async def receive_semgrep(request: Request):
    print("Request received at /receiver")
    
    # Authentication check
    auth_header = request.headers.get('Authorization')
    if auth_header != f"Bearer {os.environ.get('API_TOKEN')}":
        raise HTTPException(status_code=401, detail='Unauthorized')
    
    try:
        semgrep_data = await request.json()
        print('Received Semgrep results:', json.dumps(semgrep_data, indent=2))
        
        # Extract GitHub context from headers
        github_context = {
            'owner': request.headers.get('X-GitHub-Repository-Owner'),
            'repo': request.headers.get('X-GitHub-Repository-Name'),
            'pr_number': request.headers.get('X-GitHub-PR-Number')
        }
        
        # Only post comment if we have GitHub context and GitHub token
        if all(github_context.values()) and GITHUB_TOKEN:
            summary = create_summary(semgrep_data)
            success = await post_github_comment(github_context, summary)
            
            if success:
                print(f"✅ Posted comment to PR #{github_context['pr_number']}")
            else:
                print("❌ Failed to post GitHub comment")
        else:
            print("⚠️ Skipping GitHub comment - missing context or token")
        
        return JSONResponse(content={'status': 'success', 'message': 'Results received and processed'})
    
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

def create_summary(semgrep_data):
    """Create a summary based on your actual Semgrep data structure"""
    results = semgrep_data.get('results', [])
    
    if not results:
        return "✅ **Semgrep Architecture Scan Complete**\n\nNo issues found! Your code follows the defined architectural rules."
    
    # Group by rule ID
    issues_by_rule = {}
    for result in results:
        rule_id = result.get('check_id', 'unknown')
        if rule_id not in issues_by_rule:
            issues_by_rule[rule_id] = []
        issues_by_rule[rule_id].append(result)
    
    # Build summary
    summary = "🏗️ **Angular Architecture Scan Results**\n\n"
    summary += f"**Total Issues Found:** {len(results)}\n\n"
    
    # Process each rule
    for rule_id, rule_results in issues_by_rule.items():
        if rule_id == 'no-components-in-core':
            summary += "## 🚨 Critical Architecture Violation\n\n"
            summary += f"**Rule:** `{rule_id}`\n"
            
            # Get the message from the first result
            first_result = rule_results[0]
            message = first_result.get('extra', {}).get('message', 'Architecture violation detected')
            summary += f"**Issue:** {message}\n\n"
            
            summary += f"**Components Found in _core/ Directory ({len(rule_results)}):**\n"
            
            for issue in rule_results:
                file_path = issue.get('path', 'Unknown file')
                # Clean up the path for better readability
                clean_path = file_path.replace('property-mangement/', '')
                summary += f"- `{clean_path}`\n"
            
            summary += "\n"
            
            # Add specific guidance
            summary += "### 🔧 **Recommended Actions**\n\n"
            summary += "**Immediate Steps:**\n"
            summary += "1. Move `app.component.ts` to `src/app/` (root level)\n"
            summary += "2. Move layout components to `src/app/shared/layout/` or `src/app/layout/`\n"
            summary += "3. Keep `_core/` directory for:\n"
            summary += "   - Services (auth, api, etc.)\n"
            summary += "   - Guards and interceptors\n"
            summary += "   - Utilities and helpers\n"
            summary += "   - Models and interfaces\n\n"
            
            summary += "**Architecture Best Practice:**\n"
            summary += "```
            summary += "src/app/\n"
            summary += "├── _core/           # Services, guards, utils only\n"
            summary += "├── shared/          # Shared components\n"
            summary += "├── layout/          # Layout components\n"
            summary += "├── features/        # Feature modules\n"
            summary += "└── app.component.ts # Root component\n"
            summary += "```\n\n"
            
            summary += "**Why This Matters:**\n"
            summary += "- Maintains clear separation of concerns\n"
            summary += "- Improves code maintainability\n"
            summary += "- Follows Angular best practices\n"
            summary += "- Makes the codebase easier to navigate for team members\n"
    
    summary += "\n---\n\n"
    summary += "💡 **Next Steps:** Please address these architecture violations before merging to maintain code quality standards."
    
    return summary

async def post_github_comment(github_context, summary):
    """Post summary as GitHub PR comment"""
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Semgrep-Architecture-Bot"
    }
    
    comment_url = f"{GITHUB_API_URL}/repos/{github_context['owner']}/{github_context['repo']}/issues/{github_context['pr_number']}/comments"
    
    comment_data = {
        "body": summary
    }
    
    try:
        response = requests.post(comment_url, json=comment_data, headers=headers, timeout=30)
        return response.status_code == 201
    except Exception as e:
        print(f"Error posting GitHub comment: {str(e)}")
        return False

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
