# Flask Configuration
FLASK_ENV=production
SECRET_KEY=your-super-secret-key-change-this-in-production

# Database Configuration
# For PostgreSQL (Production)
DATABASE_URL=postgresql://innocube_user:innocube_password@localhost:5432/innocube_db

# For SQLite (Development)
# DATABASE_URL=sqlite:///innocube.db

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379
CELERY_RESULT_BACKEND=redis://localhost:6379

# Security Configuration
CORS_ORIGINS=*
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true

# Logging Configuration
LOG_LEVEL=INFO

# Upload Configuration
MAX_CONTENT_LENGTH=104857600  # 100MB in bytes
UPLOAD_FOLDER=uploads

# Email Configuration (Optional - for notifications)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Cloud Storage Configuration (Optional)
# AWS S3
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_S3_BUCKET=innocube-uploads
AWS_S3_REGION=us-east-1

# Monitoring Configuration (Optional)
SENTRY_DSN=your-sentry-dsn-here

# Rate Limiting Configuration
RATELIMIT_STORAGE_URL=redis://localhost:6379
RATELIMIT_DEFAULT=1000 per hour

# Backup Configuration
BACKUP_RETENTION_DAYS=30
AUTO_BACKUP_ENABLED=true

# Analytics Configuration
GOOGLE_ANALYTICS_ID=UA-XXXXXXXXX-X

# Domain Configuration
DOMAIN=localhost:5000
HTTPS_ENABLED=false

# Worker Configuration
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000

# Database Pool Configuration
DATABASE_POOL_SIZE=10
DATABASE_POOL_TIMEOUT=20
DATABASE_POOL_RECYCLE=3600