#!/bin/bash

# Innocube Deployment Script
# This script handles deployment to various cloud platforms

set -e

# Configuration
PROJECT_NAME="innocube"
DOCKER_IMAGE="innocube-app"
VERSION=$(date +%Y%m%d%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

# Check if required commands exist
check_dependencies() {
    log "Checking dependencies..."
    
    local deps=("docker" "docker-compose")
    for dep in "${deps[@]}"; do
        if ! command -v $dep &> /dev/null; then
            error "$dep is not installed. Please install it first."
            exit 1
        fi
    done
    
    log "All dependencies are available."
}

# Setup environment
setup_environment() {
    log "Setting up environment..."
    
    # Create necessary directories
    mkdir -p uploads logs ssl
    
    # Copy environment file if it doesn't exist
    if [ ! -f .env ]; then
        cp .env.example .env 2>/dev/null || {
            warning ".env.example not found. Creating basic .env file."
            cat > .env << EOF
FLASK_ENV=production
SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL=postgresql://innocube_user:innocube_password@db:5432/innocube_db
REDIS_URL=redis://redis:6379
CORS_ORIGINS=*
LOG_LEVEL=INFO
EOF
        }
    fi
    
    log "Environment setup complete."
}

# Build Docker images
build_images() {
    log "Building Docker images..."
    
    docker-compose build --no-cache
    
    log "Docker images built successfully."
}

# Database initialization
init_database() {
    log "Initializing database..."
    
    # Wait for database to be ready
    log "Waiting for database to be ready..."
    sleep 10
    
    # Run database migrations
    docker-compose exec web python -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('Database tables created successfully')
"
    
    log "Database initialization complete."
}

# Deploy to local environment
deploy_local() {
    log "Deploying to local environment..."
    
    # Start services
    docker-compose up -d
    
    # Wait for services to be ready
    sleep 15
    
    # Initialize database
    init_database
    
    log "Local deployment complete!"
    log "Application is running at: http://localhost"
    log "Direct Flask app: http://localhost:5000"
}

# Deploy to Heroku
deploy_heroku() {
    log "Deploying to Heroku..."
    
    # Check if Heroku CLI is installed
    if ! command -v heroku &> /dev/null; then
        error "Heroku CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Login to Heroku
    heroku auth:whoami || heroku login
    
    # Create Heroku app if it doesn't exist
    if ! heroku apps:info $PROJECT_NAME >/dev/null 2>&1; then
        log "Creating new Heroku app: $PROJECT_NAME"
        heroku create $PROJECT_NAME
    fi
    
    # Add PostgreSQL addon
    heroku addons:create heroku-postgresql:mini -a $PROJECT_NAME || true
    
    # Add Redis addon
    heroku addons:create heroku-redis:mini -a $PROJECT_NAME || true
    
    # Set environment variables
    heroku config:set FLASK_ENV=production -a $PROJECT_NAME
    heroku config:set SECRET_KEY=$(openssl rand -hex 32) -a $PROJECT_NAME
    
    # Deploy using Git
    git add .
    git commit -m "Deploy version $VERSION" || true
    heroku git:remote -a $PROJECT_NAME
    git push heroku main
    
    # Scale dynos
    heroku ps:scale web=1 worker=1 -a $PROJECT_NAME
    
    log "Heroku deployment complete!"
    log "Application URL: https://$PROJECT_NAME.herokuapp.com"
}

# Deploy to AWS (using Docker)
deploy_aws() {
    log "Deploying to AWS..."
    
    # This is a simplified AWS deployment
    # In production, you might want to use ECS, EKS, or Elastic Beanstalk
    
    warning "AWS deployment requires additional setup."
    warning "Please configure AWS CLI and update this script with your specific AWS configuration."
    
    # Example AWS ECS deployment (uncomment and configure as needed)
    # aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
    # docker tag $DOCKER_IMAGE:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/$PROJECT_NAME:latest
    # docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/$PROJECT_NAME:latest
    # aws ecs update-service --cluster innocube-cluster --service innocube-service --force-new-deployment
}

# Deploy to DigitalOcean
deploy_digitalocean() {
    log "Deploying to DigitalOcean..."
    
    # Check if doctl is installed
    if ! command -v doctl &> /dev/null; then
        error "DigitalOcean CLI (doctl) is not installed. Please install it first."
        exit 1
    fi
    
    # Create droplet if it doesn't exist
    DROPLET_NAME="$PROJECT_NAME-server"
    if ! doctl compute droplet list --format Name | grep -q $DROPLET_NAME; then
        log "Creating DigitalOcean droplet..."
        doctl compute droplet create $DROPLET_NAME \
            --size s-2vcpu-4gb \
            --image docker-20-04 \
            --region nyc1 \
            --ssh-keys $(doctl compute ssh-key list --format ID --no-header | tr '\n' ',')
        
        # Wait for droplet to be ready
        sleep 60
    fi
    
    # Get droplet IP
    DROPLET_IP=$(doctl compute droplet list --format Name,PublicIPv4 --no-header | grep $DROPLET_NAME | awk '{print $2}')
    
    if [ -z "$DROPLET_IP" ]; then
        error "Could not get droplet IP address"
        exit 1
    fi
    
    log "Deploying to droplet: $DROPLET_IP"
    
    # Copy files to droplet
    scp -r . root@$DROPLET_IP:/opt/innocube/
    
    # Deploy on droplet
    ssh root@$DROPLET_IP << EOF
        cd /opt/innocube
        docker-compose down || true
        docker-compose up -d --build
        docker-compose exec -T web python -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('Database initialized')
"
EOF
    
    log "DigitalOcean deployment complete!"
    log "Application URL: http://$DROPLET_IP"
}

# Backup database
backup_database() {
    log "Creating database backup..."
    
    BACKUP_DIR="backups"
    mkdir -p $BACKUP_DIR
    
    BACKUP_FILE="$BACKUP_DIR/innocube_backup_$(date +%Y%m%d_%H%M%S).sql"
    
    if docker-compose ps | grep -q "db.*Up"; then
        docker-compose exec -T db pg_dump -U innocube_user innocube_db > $BACKUP_FILE
        log "Database backup created: $BACKUP_FILE"
    else
        warning "Database container is not running. Skipping backup."
    fi
}

# Restore database
restore_database() {
    if [ -z "$1" ]; then
        error "Please provide backup file path"
        exit 1
    fi
    
    BACKUP_FILE="$1"
    
    if [ ! -f "$BACKUP_FILE" ]; then
        error "Backup file not found: $BACKUP_FILE"
        exit 1
    fi
    
    log "Restoring database from: $BACKUP_FILE"
    
    # Stop application
    docker-compose stop web worker scheduler
    
    # Restore database
    docker-compose exec -T db psql -U innocube_user -d innocube_db < $BACKUP_FILE
    
    # Start application
    docker-compose start web worker scheduler
    
    log "Database restore complete!"
}

# Check application health
health_check() {
    log "Performing health check..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:5000/api/stats >/dev/null 2>&1; then
            log "Health check passed!"
            return 0
        fi
        
        log "Attempt $attempt/$max_attempts failed. Waiting..."
        sleep 10
        ((attempt++))
    done
    
    error "Health check failed after $max_attempts attempts"
    return 1
}

# Monitor logs
monitor_logs() {
    log "Monitoring application logs..."
    docker-compose logs -f
}

# Clean up old images and containers
cleanup() {
    log "Cleaning up old Docker images and containers..."
    
    # Remove stopped containers
    docker container prune -f
    
    # Remove unused images
    docker image prune -f
    
    # Remove unused volumes
    docker volume prune -f
    
    log "Cleanup complete!"
}

# Update application
update() {
    log "Updating application..."
    
    # Create backup first
    backup_database
    
    # Pull latest changes
    git pull origin main
    
    # Rebuild and restart
    docker-compose down
    docker-compose up -d --build
    
    # Health check
    health_check
    
    log "Update complete!"
}

# Scale services
scale() {
    local service=$1
    local replicas=$2
    
    if [ -z "$service" ] || [ -z "$replicas" ]; then
        error "Usage: scale <service> <replicas>"
        exit 1
    fi
    
    log "Scaling $service to $replicas replicas..."
    docker-compose up -d --scale $service=$replicas
    log "Scaling complete!"
}

# Show usage
usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  local          Deploy to local environment using Docker Compose"
    echo "  heroku         Deploy to Heroku"
    echo "  aws            Deploy to AWS (requires configuration)"
    echo "  digitalocean   Deploy to DigitalOcean"
    echo "  backup         Create database backup"
    echo "  restore FILE   Restore database from backup file"
    echo "  health         Perform health check"
    echo "  logs           Monitor application logs"
    echo "  cleanup        Clean up old Docker images and containers"
    echo "  update         Update application with latest changes"
    echo "  scale SVC NUM  Scale service to specified number of replicas"
    echo "  help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 local                    # Deploy locally"
    echo "  $0 backup                   # Create backup"
    echo "  $0 restore backup.sql       # Restore from backup"
    echo "  $0 scale worker 3           # Scale worker service to 3 replicas"
}

# Main execution
main() {
    case "${1:-}" in
        "local")
            check_dependencies
            setup_environment
            build_images
            deploy_local
            health_check
            ;;
        "heroku")
            deploy_heroku
            ;;
        "aws")
            deploy_aws
            ;;
        "digitalocean")
            deploy_digitalocean
            ;;
        "backup")
            backup_database
            ;;
        "restore")
            restore_database "$2"
            ;;
        "health")
            health_check
            ;;
        "logs")
            monitor_logs
            ;;
        "cleanup")
            cleanup
            ;;
        "update")
            update
            ;;
        "scale")
            scale "$2" "$3"
            ;;
        "help"|"")
            usage
            ;;
        *)
            error "Unknown command: $1"
            usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
    