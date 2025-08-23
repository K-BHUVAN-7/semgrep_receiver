from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import os
import json
import requests
from datetime import datetime
import re

app = FastAPI()

# GitHub API configuration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')  # Add this to your Render environment
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
        
        # Extract GitHub context from the request
        github_context = extract_github_context(request)
        
        if github_context:
            # Summarize the results
            summary = summarize_semgrep_results(semgrep_data)
            
            # Post comment to GitHub PR
            await post_github_comment(github_context, summary)
        
        return JSONResponse(content={'status': 'success', 'message': 'Results received and processed'})
    
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

def extract_github_context(request: Request):
    """Extract GitHub context from request headers or data"""
    # Get GitHub context from headers (we'll add these in the workflow)
    repo_owner = request.headers.get('X-GitHub-Repository-Owner')
    repo_name = request.headers.get('X-GitHub-Repository-Name')
    pr_number = request.headers.get('X-GitHub-PR-Number')
    
    if repo_owner and repo_name and pr_number:
        return {
            'owner': repo_owner,
            'repo': repo_name,
            'pr_number': int(pr_number)
        }
    return None

def summarize_semgrep_results(semgrep_data):
    """Create a structured summary of Semgrep results"""
    results = semgrep_data.get('results', [])
    errors = semgrep_data.get('errors', [])
    
    if not results and not errors:
        return "✅ **Semgrep Security Scan Complete**\n\nNo issues found! Your code follows the defined security and architectural rules."
    
    # Group results by severity and rule
    critical_issues = [r for r in results if r.get('severity') == 'ERROR']
    warnings = [r for r in results if r.get('severity') == 'WARNING']
    info_issues = [r for r in results if r.get('severity') == 'INFO']
    
    # Group by rule ID for better organization
    issues_by_rule = {}
    for result in results:
        rule_id = result.get('check_id', 'unknown')
        if rule_id not in issues_by_rule:
            issues_by_rule[rule_id] = []
        issues_by_rule[rule_id].append(result)
    
    # Build summary
    summary = "🔍 **Semgrep Security & Architecture Scan Results**\n\n"
    
    # Overview
    total_issues = len(results)
    summary += f"**Total Issues Found:** {total_issues}\n"
    if critical_issues:
        summary += f"🚨 **Critical:** {len(critical_issues)}\n"
    if warnings:
        summary += f"⚠️ **Warnings:** {len(warnings)}\n"
    if info_issues:
        summary += f"ℹ️ **Info:** {len(info_issues)}\n"
    
    summary += "\n---\n\n"
    
    # Detailed breakdown by rule
    if critical_issues:
        summary += "## 🚨 Critical Issues (Must Fix)\n\n"
        for rule_id, rule_results in issues_by_rule.items():
            rule_critical = [r for r in rule_results if r.get('severity') == 'ERROR']
            if rule_critical:
                summary += f"### `{rule_id}`\n"
                summary += f"**Message:** {rule_critical[0].get('message', 'No message')}\n\n"
                summary += "**Affected Files:**\n"
                
                for issue in rule_critical[:5]:  # Limit to 5 files per rule
                    file_path = issue.get('path', 'Unknown file')
                    line_num = issue.get('start', {}).get('line', '?')
                    summary += f"- `{file_path}` (line {line_num})\n"
                
                if len(rule_critical) > 5:
                    summary += f"- ... and {len(rule_critical) - 5} more files\n"
                summary += "\n"
    
    if warnings:
        summary += "## ⚠️ Warnings\n\n"
        for rule_id, rule_results in issues_by_rule.items():
            rule_warnings = [r for r in rule_results if r.get('severity') == 'WARNING']
            if rule_warnings:
                summary += f"### `{rule_id}`\n"
                summary += f"**Files affected:** {len(rule_warnings)}\n"
                for issue in rule_warnings[:3]:  # Limit to 3 files per warning rule
                    file_path = issue.get('path', 'Unknown file')
                    line_num = issue.get('start', {}).get('line', '?')
                    summary += f"- `{file_path}` (line {line_num})\n"
                if len(rule_warnings) > 3:
                    summary += f"- ... and {len(rule_warnings) - 3} more\n"
                summary += "\n"
    
    # Add specific recommendations for your custom rule
    if any('no-components-in-core' in str(r.get('check_id', '')) for r in results):
        summary += "## 🔧 Recommendations\n\n"
        summary += "**Architecture Violation Detected:**\n"
        summary += "- Components found in `_core/` directory\n"
        summary += "- Move components to appropriate feature modules\n"
        summary += "- Keep `_core/` for shared services, guards, and utilities only\n\n"
    
    # Add action items
    if critical_issues:
        summary += "## 📋 Action Items\n\n"
        summary += "- [ ] Fix all critical issues before merging\n"
        summary += "- [ ] Review architectural guidelines\n"
        summary += "- [ ] Run `semgrep --config rules.yaml .` locally for detailed output\n"
    
    # Handle scan errors
    if errors:
        summary += "\n## ⚠️ Scan Errors\n\n"
        for error in errors[:3]:  # Limit error display
            summary += f"- {error.get('message', 'Unknown error')}\n"
    
    return summary

async def post_github_comment(github_context, summary):
    """Post summary as GitHub PR comment"""
    if not GITHUB_TOKEN:
        print("Warning: GITHUB_TOKEN not set, cannot post comment")
        return False
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Semgrep-Receiver"
    }
    
    # GitHub API endpoint for PR comments
    comment_url = f"{GITHUB_API_URL}/repos/{github_context['owner']}/{github_context['repo']}/issues/{github_context['pr_number']}/comments"
    
    comment_data = {
        "body": summary
    }
    
    try:
        response = requests.post(comment_url, json=comment_data, headers=headers, timeout=30)
        if response.status_code == 201:
            print(f"Successfully posted comment to PR #{github_context['pr_number']}")
            return True
        else:
            print(f"Failed to post comment: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Error posting GitHub comment: {str(e)}")
        return False

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
