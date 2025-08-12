from celery import Celery
from datetime import datetime, timedelta
import pandas as pd
import os
import logging
from app import app, db, DataProcessor
from app import Survey, SurveyResult, Respondent, Question, Answer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Celery
celery = Celery(
    app.import_name,
    broker=app.config['CELERY_BROKER_URL'],
    backend=app.config['CELERY_RESULT_BACKEND']
)

# Update Celery config with Flask app config
celery.conf.update(app.config)

class ContextTask(celery.Task):
    """Make celery tasks work with Flask app context"""
    def __call__(self, *args, **kwargs):
        with app.app_context():
            return self.run(*args, **kwargs)

celery.Task = ContextTask

@celery.task(bind=True)
def process_uploaded_file(self, file_path, original_filename):
    """
    Background task to process uploaded files
    """
    try:
        self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100, 'status': 'Starting processing...'})
        
        # Read the file
        try:
            if original_filename.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
        except Exception as e:
            raise Exception(f"Error reading file: {str(e)}")
        
        self.update_state(state='PROGRESS', meta={'current': 10, 'total': 100, 'status': 'File loaded, cleaning data...'})
        
        # Clean data
        df_clean, clean_error = DataProcessor.clean_excel_data(df)
        if clean_error:
            raise Exception(f"Data cleaning error: {clean_error}")
        
        self.update_state(state='PROGRESS', meta={'current': 30, 'total': 100, 'status': 'Data cleaned, validating...'})
        
        # Validate data
        is_valid, validation_error = DataProcessor.validate_survey_data(df_clean)
        if not is_valid:
            raise Exception(validation_error)
        
        self.update_state(state='PROGRESS', meta={'current': 50, 'total': 100, 'status': 'Processing survey data...'})
        
        # Process and insert data
        processed_count, errors = DataProcessor.process_survey_upload(df_clean)
        
        self.update_state(state='PROGRESS', meta={'current': 90, 'total': 100, 'status': 'Finalizing...'})
        
        # Clean up uploaded file
        try:
            os.remove(file_path)
        except:
            pass  # File might already be deleted
        
        return {
            'processed_count': processed_count,
            'total_rows': len(df_clean),
            'errors': errors[:10] if errors else [],
            'status': 'completed'
        }
        
    except Exception as e:
        logger.error(f"File processing error: {str(e)}")
        # Clean up file on error
        try:
            os.remove(file_path)
        except:
            pass
        raise

@celery.task
def cleanup_old_files():
    """
    Remove old uploaded files (older than 7 days)
    """
    try:
        upload_dir = app.config['UPLOAD_FOLDER']
        cutoff_date = datetime.now() - timedelta(days=7)
        
        removed_count = 0
        for filename in os.listdir(upload_dir):
            file_path = os.path.join(upload_dir, filename)
            if os.path.isfile(file_path):
                file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                if file_time < cutoff_date:
                    try:
                        os.remove(file_path)
                        removed_count += 1
                        logger.info(f"Removed old file: {filename}")
                    except Exception as e:
                        logger.error(f"Error removing file {filename}: {str(e)}")
        
        logger.info(f"Cleanup complete. Removed {removed_count} old files.")
        return {'removed_count': removed_count}
        
    except Exception as e:
        logger.error(f"Cleanup task error: {str(e)}")
        raise

@celery.task
def generate_daily_report():
    """
    Generate daily statistics report
    """
    try:
        yesterday = datetime.now() - timedelta(days=1)
        start_of_day = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Calculate daily statistics
        daily_responses = SurveyResult.query.filter(
            SurveyResult.completed_at >= start_of_day,
            SurveyResult.completed_at <= end_of_day
        ).count()
        
        new_respondents = Respondent.query.filter(
            Respondent.created_at >= start_of_day,
            Respondent.created_at <= end_of_day
        ).count()
        
        total_surveys = Survey.query.count()
        total_responses = SurveyResult.query.count()
        
        report = {
            'date': yesterday.strftime('%Y-%m-%d'),
            'daily_responses': daily_responses,
            'new_respondents': new_respondents,
            'total_surveys': total_surveys,
            'total_responses': total_responses,
            'generated_at': datetime.now().isoformat()
        }
        
        logger.info(f"Daily report generated: {report}")
        
        # Here you could save the report to a file or send via email
        # save_report_to_file(report)
        # send_report_email(report)
        
        return report
        
    except Exception as e:
        logger.error(f"Daily report generation error: {str(e)}")
        raise

@celery.task
def backup_database():
    """
    Create automated database backup
    """
    try:
        backup_dir = 'backups'
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"auto_backup_{timestamp}.sql"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # This is a simplified backup - in production you'd use proper database backup tools
        # For PostgreSQL: pg_dump
        # For SQLite: just copy the file
        
        if 'postgresql' in app.config['SQLALCHEMY_DATABASE_URI']:
            # PostgreSQL backup (requires pg_dump to be available)
            import subprocess
            result = subprocess.run([
                'pg_dump', 
                app.config['SQLALCHEMY_DATABASE_URI'],
                '-f', backup_path
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"pg_dump failed: {result.stderr}")
                
        elif 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
            # SQLite backup (simple file copy)
            import shutil
            db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
            shutil.copy2(db_path, backup_path.replace('.sql', '.db'))
        
        # Clean up old backups (keep only last 30 days)
        cutoff_date = datetime.now() - timedelta(days=30)
        for filename in os.listdir(backup_dir):
            if filename.startswith('auto_backup_'):
                file_path = os.path.join(backup_dir, filename)
                file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                if file_time < cutoff_date:
                    try:
                        os.remove(file_path)
                        logger.info(f"Removed old backup: {filename}")
                    except Exception as e:
                        logger.error(f"Error removing backup {filename}: {str(e)}")
        
        logger.info(f"Database backup created: {backup_filename}")
        return {'backup_file': backup_filename, 'status': 'completed'}
        
    except Exception as e:
        logger.error(f"Database backup error: {str(e)}")
        raise

@celery.task
def health_check_task():
    """
    Perform system health checks
    """
    try:
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'database': 'healthy',
            'redis': 'healthy',
            'disk_space': 'healthy',
            'memory': 'healthy'
        }
        
        # Check database connectivity
        try:
            db.session.execute('SELECT 1')
            db.session.commit()
        except Exception as e:
            health_status['database'] = f'unhealthy: {str(e)}'
        
        # Check disk space
        import shutil
        total, used, free = shutil.disk_usage('/')
        free_percent = (free / total) * 100
        if free_percent < 10:  # Less than 10% free space
            health_status['disk_space'] = f'warning: only {free_percent:.1f}% free'
        
        # Check memory usage
        import psutil
        memory = psutil.virtual_memory()
        if memory.percent > 90:  # More than 90% memory usage
            health_status['memory'] = f'warning: {memory.percent:.1f}% used'
        
        logger.info(f"Health check completed: {health_status}")
        
        # If any component is unhealthy, you could send alerts here
        unhealthy_components = [k for k, v in health_status.items() 
                              if isinstance(v, str) and ('unhealthy' in v or 'warning' in v)]
        
        if unhealthy_components:
            logger.warning(f"Unhealthy components detected: {unhealthy_components}")
            # send_alert_notification(health_status)
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        raise

@celery.task
def optimize_database():
    """
    Perform database optimization tasks
    """
    try:
        optimization_results = {
            'timestamp': datetime.now().isoformat(),
            'actions_performed': []
        }
        
        # Clean up old anonymous survey results (optional)
        # This is an example - adjust based on your data retention policy
        cutoff_date = datetime.now() - timedelta(days=365)  # Keep data for 1 year
        
        old_results = SurveyResult.query.filter(
            SurveyResult.completed_at < cutoff_date
        ).count()
        
        if old_results > 0:
            # In a real scenario, you might want to archive rather than delete
            logger.info(f"Found {old_results} old survey results (older than 1 year)")
            optimization_results['actions_performed'].append(f"Identified {old_results} old records for potential archival")
        
        # Update database statistics (PostgreSQL specific)
        if 'postgresql' in app.config['SQLALCHEMY_DATABASE_URI']:
            try:
                db.session.execute('ANALYZE;')
                db.session.commit()
                optimization_results['actions_performed'].append("Updated database statistics")
            except Exception as e:
                logger.error(f"Database analysis error: {str(e)}")
        
        logger.info(f"Database optimization completed: {optimization_results}")
        return optimization_results
        
    except Exception as e:
        logger.error(f"Database optimization error: {str(e)}")
        raise

# Periodic task configuration
from celery.schedules import crontab

celery.conf.beat_schedule = {
    # Clean up old files daily at 2 AM
    'cleanup-old-files': {
        'task': 'tasks.cleanup_old_files',
        'schedule': crontab(hour=2, minute=0),
    },
    
    # Generate daily report at 6 AM
    'daily-report': {
        'task': 'tasks.generate_daily_report',
        'schedule': crontab(hour=6, minute=0),
    },
    
    # Backup database daily at 3 AM
    'database-backup': {
        'task': 'tasks.backup_database',
        'schedule': crontab(hour=3, minute=0),
    },
    
    # Health check every 30 minutes
    'health-check': {
        'task': 'tasks.health_check_task',
        'schedule': crontab(minute='*/30'),
    },
    
    # Database optimization weekly on Sunday at 4 AM
    'database-optimization': {
        'task': 'tasks.optimize_database',
        'schedule': crontab(hour=4, minute=0, day_of_week=0),
    },
}

celery.conf.timezone = 'UTC'