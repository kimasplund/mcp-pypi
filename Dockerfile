FROM python:3.13-slim

WORKDIR /app

# Install required dependencies
RUN apt-get update && \
    apt-get install -y curl jq && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir packaging exceptiongroup beautifulsoup4 lxml plotly

# Copy the Python implementation
COPY pypi_tools.py /app/pypi_tools.py
RUN chmod +x /app/pypi_tools.py

# Create entry point script
RUN echo '#!/bin/bash\n\
\n\
# Function to extract argument value\n\
get_arg_value() {\n\
    local arg_name="$1"\n\
    local arg_string="$2"\n\
    echo "$arg_string" | grep -oP "$arg_name=\\K[^ ]+" | head -1\n\
}\n\
\n\
# Extract command and arguments\n\
command="$1"\n\
shift\n\
args="$@"\n\
\n\
case "$command" in\n\
    "get_package_info")\n\
        package_name=$(get_arg_value "package_name" "$args")\n\
        /app/pypi_tools.py get_package_info "$package_name"\n\
        ;;\n\
    "get_latest_version")\n\
        package_name=$(get_arg_value "package_name" "$args")\n\
        /app/pypi_tools.py get_latest_version "$package_name"\n\
        ;;\n\
    "get_package_releases")\n\
        package_name=$(get_arg_value "package_name" "$args")\n\
        /app/pypi_tools.py get_package_releases "$package_name"\n\
        ;;\n\
    "get_release_urls")\n\
        package_name=$(get_arg_value "package_name" "$args")\n\
        version=$(get_arg_value "version" "$args")\n\
        /app/pypi_tools.py get_release_urls "$package_name" "$version"\n\
        ;;\n\
    "get_source_url")\n\
        package_name=$(get_arg_value "package_name" "$args")\n\
        version=$(get_arg_value "version" "$args")\n\
        /app/pypi_tools.py get_source_url "$package_name" "$version"\n\
        ;;\n\
    "get_wheel_url")\n\
        package_name=$(get_arg_value "package_name" "$args")\n\
        version=$(get_arg_value "version" "$args")\n\
        python_tag=$(get_arg_value "python_tag" "$args")\n\
        abi_tag=$(get_arg_value "abi_tag" "$args")\n\
        platform_tag=$(get_arg_value "platform_tag" "$args")\n\
        build_tag=$(get_arg_value "build_tag" "$args")\n\
        if [ -n "$build_tag" ]; then\n\
            /app/pypi_tools.py get_wheel_url "$package_name" "$version" "$python_tag" "$abi_tag" "$platform_tag" --build-tag "$build_tag"\n\
        else\n\
            /app/pypi_tools.py get_wheel_url "$package_name" "$version" "$python_tag" "$abi_tag" "$platform_tag"\n\
        fi\n\
        ;;\n\
    "get_newest_packages")\n\
        /app/pypi_tools.py get_newest_packages\n\
        ;;\n\
    "get_latest_updates")\n\
        /app/pypi_tools.py get_latest_updates\n\
        ;;\n\
    "get_project_releases")\n\
        package_name=$(get_arg_value "package_name" "$args")\n\
        /app/pypi_tools.py get_project_releases "$package_name"\n\
        ;;\n\
    "search_packages")\n\
        query=$(get_arg_value "query" "$args")\n\
        page=$(get_arg_value "page" "$args")\n\
        if [ -n "$page" ]; then\n\
            /app/pypi_tools.py search_packages "$query" --page "$page"\n\
        else\n\
            /app/pypi_tools.py search_packages "$query"\n\
        fi\n\
        ;;\n\
    "compare_versions")\n\
        package_name=$(get_arg_value "package_name" "$args")\n\
        version1=$(get_arg_value "version1" "$args")\n\
        version2=$(get_arg_value "version2" "$args")\n\
        /app/pypi_tools.py compare_versions "$package_name" "$version1" "$version2"\n\
        ;;\n\
    "get_dependencies")\n\
        package_name=$(get_arg_value "package_name" "$args")\n\
        version=$(get_arg_value "version" "$args")\n\
        if [ -n "$version" ]; then\n\
            /app/pypi_tools.py get_dependencies "$package_name" --version "$version"\n\
        else\n\
            /app/pypi_tools.py get_dependencies "$package_name"\n\
        fi\n\
        ;;\n\
    "check_package_exists")\n\
        package_name=$(get_arg_value "package_name" "$args")\n\
        /app/pypi_tools.py check_package_exists "$package_name"\n\
        ;;\n\
    "get_package_metadata")\n\
        package_name=$(get_arg_value "package_name" "$args")\n\
        version=$(get_arg_value "version" "$args")\n\
        if [ -n "$version" ]; then\n\
            /app/pypi_tools.py get_package_metadata "$package_name" --version "$version"\n\
        else\n\
            /app/pypi_tools.py get_package_metadata "$package_name"\n\
        fi\n\
        ;;\n\
    "get_package_stats")\n\
        package_name=$(get_arg_value "package_name" "$args")\n\
        version=$(get_arg_value "version" "$args")\n\
        if [ -n "$version" ]; then\n\
            /app/pypi_tools.py get_package_stats "$package_name" --version "$version"\n\
        else\n\
            /app/pypi_tools.py get_package_stats "$package_name"\n\
        fi\n\
        ;;\n\
    "get_dependency_tree")\n\
        package_name=$(get_arg_value "package_name" "$args")\n\
        version=$(get_arg_value "version" "$args")\n\
        depth=$(get_arg_value "depth" "$args")\n\
        if [ -n "$version" ] && [ -n "$depth" ]; then\n\
            /app/pypi_tools.py get_dependency_tree "$package_name" --version "$version" --depth "$depth"\n\
        elif [ -n "$version" ]; then\n\
            /app/pypi_tools.py get_dependency_tree "$package_name" --version "$version"\n\
        elif [ -n "$depth" ]; then\n\
            /app/pypi_tools.py get_dependency_tree "$package_name" --depth "$depth"\n\
        else\n\
            /app/pypi_tools.py get_dependency_tree "$package_name"\n\
        fi\n\
        ;;\n\
    "get_documentation_url")\n\
        package_name=$(get_arg_value "package_name" "$args")\n\
        version=$(get_arg_value "version" "$args")\n\
        if [ -n "$version" ]; then\n\
            /app/pypi_tools.py get_documentation_url "$package_name" --version "$version"\n\
        else\n\
            /app/pypi_tools.py get_documentation_url "$package_name"\n\
        fi\n\
        ;;\n\
    "check_requirements_file")\n\
        file_path=$(get_arg_value "file_path" "$args")\n\
        /app/pypi_tools.py check_requirements_file "$file_path"\n\
        ;;\n\
    *)\n\
        echo "Unknown command: $command"\n\
        exit 1\n\
        ;;\n\
esac\n\
' > /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"] 