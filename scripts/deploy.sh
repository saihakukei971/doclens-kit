#!/bin/bash
# Deploy script for Business Data Integration Hub

# Exit on error
set -e

# Display help
function show_help {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -e, --env ENV           Set environment (development, production)"
    echo "  -b, --build             Build Docker image"
    echo "  -u, --up                Start containers"
    echo "  -d, --down              Stop containers"
    echo "  -r, --restart           Restart containers"
    echo "  -l, --logs              Show logs"
    echo "  -c, --clean             Clean unused Docker resources"
    echo "  --update                Pull latest code and restart"
    echo "  --backup                Create a backup"
    echo "  --restore FILE          Restore from backup file"
    echo "Examples:"
    echo "  $0 -e production -b -u  Build and start in production mode"
    echo "  $0 -r                   Restart containers"
    echo "  $0 --update             Pull latest code and restart"
}

# Default values
ENV="development"
BUILD=false
UP=false
DOWN=false
RESTART=false
LOGS=false
CLEAN=false
UPDATE=false
BACKUP=false
RESTORE=false
RESTORE_FILE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -h|--help)
            show_help
            exit 0
            ;;
        -e|--env)
            ENV="$2"
            shift
            shift
            ;;
        -b|--build)
            BUILD=true
            shift
            ;;
        -u|--up)
            UP=true
            shift
            ;;
        -d|--down)
            DOWN=true
            shift
            ;;
        -r|--restart)
            RESTART=true
            shift
            ;;
        -l|--logs)
            LOGS=true
            shift
            ;;
        -c|--clean)
            CLEAN=true
            shift
            ;;
        --update)
            UPDATE=true
            shift
            ;;
        --backup)
            BACKUP=true
            shift
            ;;
        --restore)
            RESTORE=true
            RESTORE_FILE="$2"
            shift
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check environment
if [[ "$ENV" != "development" && "$ENV" != "production" ]]; then
    echo "Invalid environment: $ENV. Must be 'development' or 'production'."
    exit 1
fi

# Set environment variable for Docker Compose
export ENV_FOR_DYNACONF=$ENV

# Script directory (for relative paths)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_DIR"

# Update from git repository
if [[ "$UPDATE" == true ]]; then
    echo "========== Updating from git repository =========="
    git pull
    BUILD=true
    RESTART=true
fi

# Create backup
if [[ "$BACKUP" == true ]]; then
    echo "========== Creating backup =========="
    BACKUP_DIR="backups"
    mkdir -p "$BACKUP_DIR"
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.tar.gz"
    
    # Create archive
    tar -czf "$BACKUP_FILE" \
        --exclude="data/documents/temp" \
        --exclude="*.git" \
        --exclude="*.log" \
        --exclude="__pycache__" \
        --exclude="*.pyc" \
        config data
    
    echo "Backup created: $BACKUP_FILE"
fi

# Restore from backup
if [[ "$RESTORE" == true ]]; then
    if [[ ! -f "$RESTORE_FILE" ]]; then
        echo "Backup file not found: $RESTORE_FILE"
        exit 1
    fi
    
    echo "========== Restoring from backup: $RESTORE_FILE =========="
    
    # Stop containers if running
    docker-compose down
    
    # Extract backup archive
    tar -xzf "$RESTORE_FILE"
    
    echo "Restore completed. Start the application with: $0 -u"
    exit 0
fi

# Build Docker image
if [[ "$BUILD" == true ]]; then
    echo "========== Building Docker image ($ENV mode) =========="
    docker-compose build
fi

# Stop containers
if [[ "$DOWN" == true ]]; then
    echo "========== Stopping containers =========="
    docker-compose down
fi

# Start containers
if [[ "$UP" == true ]]; then
    echo "========== Starting containers ($ENV mode) =========="
    docker-compose up -d
fi

# Restart containers
if [[ "$RESTART" == true ]]; then
    echo "========== Restarting containers ($ENV mode) =========="
    docker-compose restart
fi

# Show logs
if [[ "$LOGS" == true ]]; then
    echo "========== Showing logs =========="
    docker-compose logs -f
fi

# Clean Docker resources
if [[ "$CLEAN" == true ]]; then
    echo "========== Cleaning Docker resources =========="
    
    # Remove unused containers
    echo "Removing unused containers..."
    docker container prune -f
    
    # Remove unused images
    echo "Removing unused images..."
    docker image prune -f
    
    # Remove unused volumes
    echo "Removing unused volumes..."
    docker volume prune -f
    
    # Remove unused networks
    echo "Removing unused networks..."
    docker network prune -f
    
    echo "Docker cleanup completed."
fi

echo "Done."