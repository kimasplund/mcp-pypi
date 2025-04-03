    async def check_requirements_file(self, file_path: str) -> PackageRequirementsResult:
        """Check a requirements file for updates to dependencies."""
        path = Path(file_path)
        
        if not path.exists():
            return cast(PackageRequirementsResult, format_error(ErrorCode.FILE_NOT_FOUND, f"File not found: {file_path}"))
        
        try:
            with open(path, "r") as f:
                file_content = f.read()
        except Exception as e:
            return cast(PackageRequirementsResult, format_error(ErrorCode.READ_ERROR, f"Error reading file: {str(e)}"))
        
        requirements = []
        
        # Check file extension and parse accordingly
        if path.name.endswith(('.txt', '.pip')):
            reqs = self._parse_requirements_txt(file_content)
            for req_str in reqs:
                try:
                    req = Requirement(req_str)
                    requirements.append(req)
                except Exception:
                    # Skip invalid requirements
                    continue
        elif path.name.endswith('.toml'):
            reqs = self._check_pyproject_toml(file_content)
            for req_str in reqs:
                try:
                    req = Requirement(req_str)
                    requirements.append(req)
                except Exception:
                    # Skip invalid requirements
                    continue
        else:
            return cast(PackageRequirementsResult, format_error(ErrorCode.INVALID_INPUT, f"File must be a .txt, .pip, or .toml file: {file_path}"))
        
        packages = []
        for req in requirements:
            package_name = sanitize_package_name(req.name)
            package_info = await self.get_package_info(package_name)
            
            if not package_info["success"]:
                packages.append({
                    "name": req.name,
                    "specs": str(req.specifier) if req.specifier else "",
                    "current_version": "",
                    "latest_version": "",
                    "is_up_to_date": False,
                    "is_compatible": False
                })
                continue
            
            releases = package_info["data"]["releases"]
            latest_version = package_info["data"]["info"]["version"]
            
            # Determine current version by finding the highest version that matches the specifier
            current_version = ""
            if req.specifier:
                filtered_releases = [r for r in releases if req.specifier.contains(r)]
                if filtered_releases:
                    current_version = max(filtered_releases, key=lambda v: Version(v))
            
            # If no current version is found but specifier exists, check if any pre-releases match
            if not current_version and req.specifier:
                filtered_releases = [
                    r for r in releases 
                    if Version(r).is_prerelease and req.specifier.contains(r)
                ]
                if filtered_releases:
                    current_version = max(filtered_releases, key=lambda v: Version(v))
            
            # If still no current version but latest version satisfies the specifier, use that
            if not current_version and req.specifier and req.specifier.contains(latest_version):
                current_version = latest_version
            
            # If no specifier or no matching version, use latest
            if not current_version:
                current_version = latest_version
            
            is_up_to_date = current_version == latest_version
            is_compatible = True if not req.specifier else req.specifier.contains(latest_version)
            
            packages.append({
                "name": req.name,
                "specs": str(req.specifier) if req.specifier else "",
                "current_version": current_version,
                "latest_version": latest_version,
                "is_up_to_date": is_up_to_date,
                "is_compatible": is_compatible
            })
        
        return {
            "success": True,
            "message": f"Found {len(packages)} package(s) in requirements file",
            "data": {
                "file_path": file_path,
                "packages": packages
            }
        } 