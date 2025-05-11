#!/bin/bash
# Setup cron jobs for Business Data Integration Hub

# Exit on error
set -e

# Script directory (for relative paths)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Container name
CONTAINER_NAME="data_hub"

# Display help
function show_help {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -i, --install           Install cron jobs"
    echo "  -r, --remove            Remove cron jobs"
    echo "  -l, --list              List current cron jobs"
    echo "Examples:"
    echo "  $0 -i                   Install cron jobs"
    echo "  $0 -r                   Remove cron jobs"
    echo "  $0 -l                   List current cron jobs"
}

# Default values
INSTALL=false
REMOVE=false
LIST=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -h|--help)
            show_help
            exit 0
            ;;
        -i|--install)
            INSTALL=true
            shift
            ;;
        -r|--remove)
            REMOVE=true
            shift
            ;;
        -l|--list)
            LIST=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Show current cron jobs
if [[ "$LIST" == true ]]; then
    echo "Current cron jobs:"
    crontab -l 2>/dev/null || echo "No crontab for $(whoami)"
    exit 0
fi

# Remove cron jobs
if [[ "$REMOVE" == true ]]; then
    echo "Removing cron jobs for Business Data Integration Hub..."
    
    # Create a temporary file
    TEMP_CRON=$(mktemp)
    
    # Export current crontab and filter out our jobs
    crontab -l 2>/dev/null | grep -v "$CONTAINER_NAME" > "$TEMP_CRON" || true
    
    # Install new crontab
    crontab "$TEMP_CRON"
    rm "$TEMP_CRON"
    
    echo "Cron jobs removed."
    exit 0
fi

# Install cron jobs
if [[ "$INSTALL" == true ]]; then
    echo "Installing cron jobs for Business Data Integration Hub..."
    
    # Create a temporary file
    TEMP_CRON=$(mktemp)
    
    # Export current crontab
    crontab -l 2>/dev/null > "$TEMP_CRON" || true
    
    # Remove existing jobs for our application
    grep -v "$CONTAINER_NAME" "$TEMP_CRON" > "${TEMP_CRON}.new" || true
    mv "${TEMP_CRON}.new" "$TEMP_CRON"
    
    # Add header
    echo "# Business Data Integration Hub cron jobs" >> "$TEMP_CRON"
    
    # Add monthly archive job (runs on 1st day of each month at 1:00 AM)
    echo "0 1 1 * * docker exec $CONTAINER_NAME python -m scripts.archive_task" >> "$TEMP_CRON"
    
    # Add weekly database vacuum job (runs every Sunday at 2:00 AM)
    echo "0 2 * * 0 docker exec $CONTAINER_NAME python -m app.services.archiver vacuum_database" >> "$TEMP_CRON"
    
    # Add daily backup job (runs every day at 3:00 AM)
    echo "0 3 * * * docker exec $CONTAINER_NAME python -m scripts.backup" >> "$TEMP_CRON"
    
    # Add weekly cleanup job for deleted documents (runs every Sunday at 4:00 AM)
    echo "0 4 * * 0 docker exec $CONTAINER_NAME python -m app.services.archiver purge_deleted_documents 30" >> "$TEMP_CRON"
    
    # Install new crontab
    crontab "$TEMP_CRON"
    rm "$TEMP_CRON"
    
    echo "Cron jobs installed. To see them, run: $0 -l"
    exit 0
fi

# If no option specified, show help
show_help
exit 1