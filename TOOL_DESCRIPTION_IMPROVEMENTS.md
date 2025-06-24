# Tool Description Improvements for Better LLM Guidance

## Problem Analysis
When LLMs use our security tools, they often:
1. Only update one file (requirements.txt) when dependencies exist in multiple files
2. Don't automatically apply the recommended security fixes
3. Miss the need to maintain consistency across all dependency files

## Proposed Improvements

### 1. Enhanced Tool Descriptions with Action Directives

#### check_requirements_txt / check_pyproject_toml
```python
"""
🎯 Analyze {file_type} for outdated packages and security issues.

⚠️ IMPORTANT ACTIONS AFTER RUNNING THIS TOOL:
1. If vulnerabilities are found with recommendations → UPDATE the constraints in this file
2. ALWAYS check for other dependency files → Run check on pyproject.toml, setup.py, setup.cfg
3. Ensure consistency → All files should have matching version constraints

Returns:
    PackageRequirementsResult with:
    - outdated: Packages with security recommendations (UPDATE THESE!)
    - up_to_date: Secure packages
    - recommendation: Specific version to update to

Example workflow:
    1. check_requirements_txt("/path/requirements.txt")
    2. If outdated packages found → Edit file with recommended versions
    3. check_pyproject_toml("/path/pyproject.toml") 
    4. Ensure both files have matching constraints
    5. Commit with message mentioning all files updated

⚠️ WARNING: Dependencies may be specified in multiple files:
   - requirements.txt
   - pyproject.toml ([project.dependencies])
   - setup.py (install_requires)
   - setup.cfg ([options] install_requires)
   Always check ALL files for consistency!
"""
```

### 2. Enhanced Output Format

Update the tool output to include actionable next steps:

```python
{
    "outdated": [...],
    "up_to_date": [...],
    "next_actions": [
        {
            "action": "update_file",
            "file": "/path/requirements.txt",
            "changes": [
                {"package": "aiohttp", "from": ">=3.8.0", "to": ">=3.12.13"},
                {"package": "pydantic", "from": ">=2.0.0", "to": ">=2.11.7"}
            ]
        },
        {
            "action": "check_other_files",
            "files": ["/path/pyproject.toml", "/path/setup.py"],
            "reason": "Ensure dependency consistency across all files"
        }
    ],
    "consistency_warning": "Dependencies found in multiple files - update all for consistency"
}
```

### 3. New Tool: sync_dependencies

```python
@self.mcp_server.tool()
async def sync_dependencies(project_path: str, dry_run: bool = True) -> DependencySyncResult:
    """
    🔄 Synchronize dependency versions across all project files.
    
    This tool ensures consistency by:
    1. Finding all files with dependencies (requirements.txt, pyproject.toml, setup.py, etc.)
    2. Identifying version mismatches between files
    3. Recommending or applying updates to use the most secure version everywhere
    
    Args:
        project_path: Root directory of the project
        dry_run: If True, only show what would be changed. If False, apply changes.
        
    Returns:
        DependencySyncResult with:
        - files_found: List of dependency files discovered
        - inconsistencies: Mismatched versions between files
        - security_updates: Required updates for security
        - actions_taken: Changes made (if dry_run=False)
        
    Example:
        sync_dependencies("/home/user/project", dry_run=True)
        → Shows all inconsistencies and required updates
        
        sync_dependencies("/home/user/project", dry_run=False) 
        → Applies all security updates and ensures consistency
    
    ⚡ This is the RECOMMENDED tool to use after any security scan!
    """
```

### 4. Updated security_audit_project Description

```python
"""
🛡️🔍 Comprehensive security audit of an entire Python project.

[existing description...]

📋 POST-AUDIT CHECKLIST:
If vulnerabilities are found, you MUST:
1. ✅ Update ALL dependency files (not just requirements.txt)
2. ✅ Run sync_dependencies() to ensure consistency
3. ✅ Test the updates don't break functionality
4. ✅ Commit with clear message listing all updated files

⚠️ COMMON MISTAKE: Only updating requirements.txt when dependencies 
   are also in pyproject.toml. Always update ALL files!

Returns:
    [existing return description...]
    - files_to_update: List of files that need security updates
    - update_commands: Specific commands to run for fixes
"""
```

## Implementation Changes Needed

### 1. Update Tool Return Values
Add `next_actions` and `files_to_update` fields to guide LLMs on what to do next.

### 2. Add Consistency Checking
When checking one file, detect if other dependency files exist and remind to check them.

### 3. Create sync_dependencies Tool
Implement a tool that handles the complete update workflow across all files.

### 4. Enhance Recommendations
Instead of just saying "Update constraint to >=X", provide the exact edit commands or patches.

## Example Enhanced Workflow

When an LLM uses our tools with these improvements:

1. LLM runs `check_requirements_txt()`
2. Tool returns vulnerabilities AND next_actions
3. LLM sees explicit instruction to update ALL files
4. LLM automatically checks pyproject.toml
5. LLM uses sync_dependencies() to ensure consistency
6. All files are updated in one session

This eliminates the current problem where LLMs stop after updating just one file.