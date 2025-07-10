#!/bin/bash

# Meeting Agents System Deployment Script
# This script handles the complete deployment of the meeting agents system

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="meeting-agents"
DOCKER_IMAGE="meeting-agents:latest"
CONTAINER_NAME="meeting-agents-app"
PORT=5000

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_requirements() {
    log_info "Checking deployment requirements..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if running as root (for Docker permissions)
    if [ "$EUID" -eq 0 ]; then
        log_warning "Running as root. Make sure Docker permissions are properly configured."
    fi
    
    log_success "Requirements check passed"
}

setup_environment() {
    log_info "Setting up environment..."
    
    # Change to project root
    cd "$PROJECT_ROOT"
    
    # Create .env file if it doesn't exist
    if [ ! -f .env ]; then
        log_info "Creating .env file..."
        cat > .env << EOF
# API Keys (REQUIRED - Add your actual keys)
OPENAI_API_KEY=your-openai-key-here
GOOGLE_APPLICATION_CREDENTIALS=credentials.json

# Application settings
FLASK_ENV=production
FLASK_SECRET_KEY=$(openssl rand -hex 32)
DEBUG=false

# Database (if using PostgreSQL)
POSTGRES_PASSWORD=$(openssl rand -hex 16)

# NANDA settings
NANDA_REGISTRY_URL=https://nanda-registry.com
EOF
        log_warning "Please edit .env file and add your actual API keys"
        log_warning "You need: OPENAI_API_KEY and Google credentials"
    fi
    
    # Check if credentials.json exists
    if [ ! -f credentials.json ]; then
        log_warning "credentials.json not found."
        log_warning "Please add your Google Calendar API credentials to credentials.json"
        log_warning "Download from: https://console.cloud.google.com/"
    fi
    
    # Create necessary directories
    mkdir -p logs frontend/static/uploads
    
    log_success "Environment setup completed"
}

build_application() {
    log_info "Building application..."
    
    # Change to deployment directory for docker-compose
    cd "$SCRIPT_DIR"
    
    # Build Docker image using docker-compose
    docker-compose build
    
    log_success "Application built successfully"
}

deploy_services() {
    log_info "Deploying services..."
    
    # Change to deployment directory
    cd "$SCRIPT_DIR"
    
    # Stop existing services
    docker-compose down 2>/dev/null || true
    
    # Start services
    docker-compose up -d
    
    # Wait for services to be ready
    log_info "Waiting for services to start..."
    sleep 10
    
    # Check health
    for i in {1..30}; do
        if curl -f http://localhost:$PORT/api/health >/dev/null 2>&1; then
            log_success "Application is healthy and ready!"
            break
        fi
        
        if [ $i -eq 30 ]; then
            log_error "Application failed to start properly"
            docker-compose logs
            exit 1
        fi
        
        log_info "Waiting for application to be ready... ($i/30)"
        sleep 2
    done
    
    log_success "Services deployed successfully"
}

run_tests() {
    log_info "Running integration tests..."
    
    # Wait a bit more for everything to stabilize
    sleep 5
    
    # Change to deployment directory
    cd "$SCRIPT_DIR"
    
    # Run tests inside container
    if docker-compose exec -T meeting-agents python testing/test_system.py; then
        log_success "All tests passed!"
    else
        log_warning "Some tests failed, but deployment continues"
        log_warning "Check logs: docker-compose logs meeting-agents"
    fi
}

register_with_nanda() {
    log_info "Registering agents with NANDA..."
    
    # Make API call to register with NANDA
    if curl -X POST http://localhost:$PORT/api/nanda/register >/dev/null 2>&1; then
        log_success "Agents registered with NANDA"
    else
        log_warning "NANDA registration failed (this is optional)"
        log_warning "You can register manually later via the web interface"
    fi
}

show_deployment_info() {
    log_success "🚀 Meeting Agents System Deployed Successfully!"
    echo
    echo "📍 Access Points:"
    echo "   Web Interface: http://localhost:$PORT"
    echo "   API Health:    http://localhost:$PORT/api/health"
    echo "   API Docs:      http://localhost:$PORT/api"
    echo
    echo "🐳 Docker Commands:"
    echo "   View logs:     cd deployment && docker-compose logs -f"
    echo "   Stop system:   cd deployment && docker-compose down"
    echo "   Restart:       cd deployment && docker-compose restart"
    echo "   Update:        git pull && ./deployment/deploy.sh"
    echo
    echo "📊 Service Status:"
    cd "$SCRIPT_DIR"
    docker-compose ps
    echo
    echo "🔧 Configuration:"
    echo "   Environment:   .env file (in project root)"
    echo "   Credentials:   credentials.json (in project root)"
    echo "   Logs:          ./logs/ directory"
    echo
    if [ ! -f "$PROJECT_ROOT/credentials.json" ]; then
        echo "⚠️  Don't forget to:"
        echo "   1. Add your OpenAI API key to .env"
        echo "   2. Add Google Calendar credentials to credentials.json"
        echo "   3. Restart: cd deployment && docker-compose restart"
    fi
}

cleanup_old_deployment() {
    log_info "Cleaning up old deployment..."
    
    # Change to deployment directory
    cd "$SCRIPT_DIR"
    
    # Remove old containers
    docker container rm -f $CONTAINER_NAME 2>/dev/null || true
    
    # Clean up unused images
    docker image prune -f
    
    log_success "Cleanup completed"
}

backup_data() {
    log_info "Creating backup..."
    
    # Change to project root
    cd "$PROJECT_ROOT"
    
    BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # Backup logs
    cp -r logs "$BACKUP_DIR/" 2>/dev/null || true
    
    # Backup environment (without secrets)
    if [ -f .env.example ]; then
        cp .env.example "$BACKUP_DIR/" 2>/dev/null || true
    fi
    
    log_success "Backup created: $BACKUP_DIR"
}

# Main deployment function
main() {
    echo "🚀 Meeting Agents System Deployment"
    echo "======================================"
    echo "📁 Project Root: $PROJECT_ROOT"
    echo "📁 Script Dir:   $SCRIPT_DIR"
    echo
    
    # Parse command line arguments
    case "${1:-deploy}" in
        "deploy")
            check_requirements
            setup_environment
            cleanup_old_deployment
            build_application
            deploy_services
            run_tests
            register_with_nanda
            show_deployment_info
            ;;
        "build")
            build_application
            ;;
        "start")
            cd "$SCRIPT_DIR"
            docker-compose up -d
            log_success "Services started"
            ;;
        "stop")
            cd "$SCRIPT_DIR"
            docker-compose down
            log_success "Services stopped"
            ;;
        "restart")
            cd "$SCRIPT_DIR"
            docker-compose restart
            log_success "Services restarted"
            ;;
        "logs")
            cd "$SCRIPT_DIR"
            docker-compose logs -f
            ;;
        "test")
            run_tests
            ;;
        "backup")
            backup_data
            ;;
        "clean")
            cleanup_old_deployment
            cd "$SCRIPT_DIR"
            docker-compose down
            docker volume prune -f
            log_success "Cleanup completed"
            ;;
        "status")
            cd "$SCRIPT_DIR"
            docker-compose ps
            echo
            curl -s http://localhost:$PORT/api/health | python -m json.tool 2>/dev/null || echo "Service not responding"
            ;;
        "update")
            log_info "Updating system..."
            cd "$PROJECT_ROOT"
            git pull
            cd "$SCRIPT_DIR"
            docker-compose down
            build_application
            deploy_services
            log_success "Update completed"
            ;;
        *)
            echo "Usage: $0 {deploy|build|start|stop|restart|logs|test|backup|clean|status|update}"
            echo
            echo "Commands:"
            echo "  deploy   - Full deployment (default)"
            echo "  build    - Build Docker image only"
            echo "  start    - Start services"
            echo "  stop     - Stop services"
            echo "  restart  - Restart services"
            echo "  logs     - View logs"
            echo "  test     - Run tests"
            echo "  backup   - Create backup"
            echo "  clean    - Clean up old deployments"
            echo "  status   - Show service status"
            echo "  update   - Update and redeploy"
            echo
            echo "📁 Script should be run from: deployment/deploy.sh"
            echo "📁 Or from project root:     ./deployment/deploy.sh"
            exit 1
            ;;
    esac
}

# Make script executable and run
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi