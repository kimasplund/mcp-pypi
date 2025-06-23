"""Enhanced tool descriptions for PyPI MCP Server.

This module contains improved tool descriptions that are more enticing 
and clear for LLMs to understand and utilize effectively.
"""

TOOL_DESCRIPTIONS = {
    "search_python_packages": {
        "name": "search_python_packages",
        "description": """🔍 Search PyPI (Python Package Index) to instantly discover Python libraries and packages for any task.
        
        Perfect for: Finding packages for specific functionality, exploring alternatives, discovering new tools.
        Returns: Ranked list of packages with names, descriptions, and latest versions.
        
        Example uses:
        - "Find packages for web scraping" → beautifulsoup4, scrapy, requests-html
        - "Search for machine learning libraries" → scikit-learn, tensorflow, pytorch
        - "Discover testing frameworks" → pytest, unittest, nose2
        """,
        "short": "Search for Python packages on PyPI"
    },
    
    "get_python_package_info": {
        "name": "get_python_package_info", 
        "description": """📦 Get comprehensive details about any Python package from PyPI including description, author, license, and more.
        
        Perfect for: Understanding what a package does, checking licensing, viewing project URLs.
        Returns: Complete package metadata including summary, keywords, classifiers, and links.
        
        Use this when you need to:
        - Understand a package's purpose and features
        - Check license compatibility
        - Find documentation and source code links
        - See package maintainer information
        """,
        "short": "Get detailed PyPI package information"
    },
    
    "get_python_package_latest_version": {
        "name": "get_python_package_latest_version",
        "description": """🚀 Check the latest available version of any Python package on PyPI.
        
        Perfect for: Version updates, compatibility checks, staying current.
        Returns: Latest stable version number with release date.
        
        Use this to:
        - Check if updates are available
        - Verify version compatibility
        - Stay informed about package releases
        """,
        "short": "Check latest Python package version on PyPI"
    },
    
    "get_python_package_dependencies": {
        "name": "get_python_package_dependencies",
        "description": """🔗 Analyze Python package dependencies from PyPI to understand requirements and potential conflicts.
        
        Perfect for: Dependency management, security audits, installation planning.
        Returns: Complete list of required and optional dependencies with version constraints.
        
        Essential for:
        - Planning installations in restricted environments
        - Identifying potential version conflicts
        - Understanding package complexity
        - Security dependency scanning
        """,
        "short": "Analyze Python package dependencies from PyPI"
    },
    
    "get_python_dependency_tree": {
        "name": "get_python_dependency_tree",
        "description": """🌳 Visualize the complete dependency tree showing all transitive dependencies.
        
        Perfect for: Deep dependency analysis, security audits, optimization.
        Returns: Nested tree structure showing all dependencies and sub-dependencies.
        
        Invaluable for:
        - Identifying deep dependency chains
        - Finding common dependencies across packages
        - Detecting circular dependencies
        - Optimizing project dependencies
        """,
        "short": "Map Python package dependency trees from PyPI"
    },
    
    "get_python_package_stats": {
        "name": "get_python_package_stats",
        "description": """📊 Access PyPI download statistics to gauge Python package popularity and adoption trends.
        
        Perfect for: Evaluating package reliability, comparing alternatives, trend analysis.
        Returns: Download counts by day, week, and month with historical trends.
        
        Use to:
        - Assess package popularity and community size
        - Compare adoption between alternatives
        - Track growth trends over time
        - Make informed package selection decisions
        """,
        "short": "Get PyPI download statistics for Python packages"
    },
    
    "check_python_package_exists": {
        "name": "check_python_package_exists",
        "description": """✅ Quickly verify if a Python package name exists on PyPI (Python Package Index).
        
        Perfect for: Name validation, availability checks, typo detection.
        Returns: Boolean confirmation of package existence.
        
        Essential for:
        - Validating package names before installation
        - Checking name availability for new packages
        - Detecting typos in requirements
        """,
        "short": "Verify if a Python package exists on PyPI"
    },
    
    "compare_python_package_versions": {
        "name": "compare_python_package_versions",
        "description": """🔄 Compare two versions of a Python package to understand differences and compatibility.
        
        Perfect for: Upgrade planning, compatibility checks, changelog analysis.
        Returns: Version comparison with semantic versioning analysis.
        
        Use when:
        - Planning version upgrades
        - Checking breaking changes
        - Understanding version relationships
        """,
        "short": "Compare Python package versions from PyPI"
    },
    
    "check_python_requirements_file": {
        "name": "check_python_requirements_file",
        "description": """📋 Analyze Python requirements.txt files to find outdated PyPI packages and security updates.
        
        Perfect for: Dependency audits, security scanning, update management.
        Returns: List of packages with current vs latest versions, update recommendations.
        
        Automates:
        - Finding outdated dependencies
        - Identifying security updates
        - Suggesting compatible upgrades
        - Validating requirement specifications
        """,
        "short": "Audit Python requirements.txt for PyPI updates"
    },
    
    "check_python_pyproject_toml": {
        "name": "check_python_pyproject_toml",
        "description": """🎯 Analyze pyproject.toml Python dependencies from PyPI for modern Python projects.
        
        Perfect for: Modern project audits, Poetry/PEP 517 projects, build system checks.
        Returns: Dependency analysis with update recommendations for all dependency groups.
        
        Supports:
        - PEP 621 dependencies
        - Poetry dependencies and dev-dependencies
        - Build system requirements
        - Optional dependency groups
        """,
        "short": "Analyze Python pyproject.toml for PyPI updates"
    },
    
    "get_python_package_changelog": {
        "name": "get_python_package_changelog",
        "description": """📝 Extract and view Python package changelogs from PyPI to understand what's new.
        
        Perfect for: Update decisions, feature discovery, breaking change identification.
        Returns: Parsed changelog with version history and changes.
        
        Helps you:
        - Understand new features before upgrading
        - Identify breaking changes
        - Track bug fixes and improvements
        - Make informed update decisions
        """,
        "short": "View Python package changelogs from PyPI"
    },
    
    "check_python_package_vulnerabilities": {
        "name": "check_python_package_vulnerabilities",
        "description": """🛡️ Scan Python packages for known security vulnerabilities and CVEs.
        
        Perfect for: Security audits, compliance checks, risk assessment.
        Returns: List of vulnerabilities with severity levels and remediation advice.
        
        Critical for:
        - Security compliance requirements
        - Protecting against known exploits
        - Prioritizing security updates
        - Risk management decisions
        """,
        "short": "Scan Python packages for security vulnerabilities"
    },
    
    "get_python_package_release_history": {
        "name": "get_python_package_release_history",
        "description": """📅 View complete release history with dates and version progression.
        
        Perfect for: Understanding release cadence, stability assessment, historical analysis.
        Returns: Chronological list of all releases with dates and version numbers.
        
        Useful for:
        - Assessing project maintenance activity
        - Understanding release patterns
        - Evaluating project stability
        - Historical version tracking
        """,
        "short": "View Python package release history from PyPI"
    },
    
    "get_python_package_metadata": {
        "name": "get_python_package_metadata",
        "description": """📋 Access complete metadata for any Python package on PyPI.
        
        Perfect for: Package analysis, license checking, platform compatibility.
        Returns: Full metadata including classifiers, keywords, requirements, and more.
        
        Provides:
        - License information
        - Platform compatibility  
        - Python version requirements
        - Package classifiers and keywords
        """,
        "short": "Get complete PyPI metadata for Python packages"
    },
    
    "list_python_package_versions": {
        "name": "list_python_package_versions",
        "description": """📚 List all available versions of a Python package on PyPI.
        
        Perfect for: Version selection, downgrade options, historical reference.
        Returns: Complete list of all published versions in chronological order.
        
        Use for:
        - Finding specific older versions
        - Understanding version history
        - Planning downgrades if needed
        - Checking pre-release versions
        """,
        "short": "List all PyPI versions of a Python package"
    },
    
    "get_python_package_documentation": {
        "name": "get_python_package_documentation",
        "description": """📖 Find documentation links for Python packages from PyPI.
        
        Perfect for: Learning new packages, finding examples, API references.
        Returns: Official documentation URLs, readmes, and getting started guides.
        
        Helps locate:
        - Official documentation sites
        - API references
        - Tutorial links
        - Example code repositories
        """,
        "short": "Find documentation for Python packages"
    },
    
    "get_newest_python_packages": {
        "name": "get_newest_python_packages",
        "description": """🆕 Discover the newest Python packages just published to PyPI.
        
        Perfect for: Staying current, finding emerging tools, trend spotting.
        Returns: List of recently published packages with descriptions.
        
        Great for:
        - Discovering cutting-edge tools
        - Monitoring Python ecosystem trends
        - Finding fresh solutions
        - Exploring new technologies
        """,
        "short": "Discover newest Python packages on PyPI"
    },
    
    "get_python_package_updates": {
        "name": "get_python_package_updates", 
        "description": """🔄 Track recent updates to Python packages on PyPI.
        
        Perfect for: Monitoring updates, tracking releases, staying informed.
        Returns: Recent package updates with version changes and dates.
        
        Monitor:
        - Package update frequency
        - New releases from favorites
        - Breaking changes
        - Security patches
        """,
        "short": "Track recent Python package updates on PyPI"
    },
    
    "get_python_package_releases": {
        "name": "get_python_package_releases",
        "description": """📢 View the latest releases across all Python packages on PyPI.
        
        Perfect for: Monitoring ecosystem activity, tracking major releases.
        Returns: Recent releases with package names, versions, and dates.
        
        Stay informed about:
        - Major version releases
        - Popular package updates
        - New stable releases
        - Community activity
        """,
        "short": "View latest Python package releases on PyPI"
    }
}

# Server description for the MCP server itself
SERVER_DESCRIPTION = """🐍 PyPI MCP Server - Your Python Package Intelligence Assistant

Access PyPI's vast ecosystem of 500,000+ packages with powerful tools for search, analysis, and dependency management. 

Key capabilities:
• 🔍 Smart package search and discovery
• 📊 Download statistics and popularity metrics  
• 🔗 Deep dependency analysis and visualization
• 🛡️ Security vulnerability scanning
• 📋 Requirements file auditing
• 🚀 Version comparison and update recommendations

Perfect for developers who need to:
- Find the right packages for their projects
- Manage and audit dependencies
- Stay secure with vulnerability scanning
- Keep projects up-to-date
- Make informed package choices

All data comes directly from PyPI's official APIs with intelligent caching for fast responses.
"""