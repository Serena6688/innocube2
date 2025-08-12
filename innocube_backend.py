from flask import Flask, request, jsonify, render_template, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.utils import secure_filename
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import json
from io import BytesIO
import re
import logging
from sqlalchemy import text, func

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:password@localhost/innocube_db'
# For development, you can use SQLite:
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///innocube.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# Database Models
class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100))
    brand = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    sales = db.relationship('Sale', backref='product', lazy=True)
    surveys = db.relationship('Survey', backref='product', lazy=True)

class Sale(db.Model):
    __tablename__ = 'sales'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    revenue = db.Column(db.Float, nullable=False)
    sale_date = db.Column(db.Date, nullable=False)
    region = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Respondent(db.Model):
    __tablename__ = 'respondents'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True)
    age_group = db.Column(db.String(50))
    gender = db.Column(db.String(20))
    location = db.Column(db.String(100))
    income_level = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    survey_results = db.relationship('SurveyResult', backref='respondent', lazy=True)

class Survey(db.Model):
    __tablename__ = 'surveys'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    version = db.Column(db.String(50), default='v1')
    status = db.Column(db.String(50), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    questions = db.relationship('Question', backref='survey', lazy=True)
    survey_results = db.relationship('SurveyResult', backref='survey', lazy=True)

class Question(db.Model):
    __tablename__ = 'questions'
    
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('surveys.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(50), nullable=False)  # multiple_choice, text, rating, etc.
    order_num = db.Column(db.Integer, nullable=False)
    is_required = db.Column(db.Boolean, default=True)
    
    # Relationships
    options = db.relationship('QuestionOption', backref='question', lazy=True)
    answers = db.relationship('Answer', backref='question', lazy=True)

class QuestionOption(db.Model):
    __tablename__ = 'question_options'
    
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    option_text = db.Column(db.String(255), nullable=False)
    option_value = db.Column(db.String(100))
    order_num = db.Column(db.Integer, nullable=False)

class SurveyResult(db.Model):
    __tablename__ = 'survey_results'
    
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('surveys.id'), nullable=False)
    respondent_id = db.Column(db.Integer, db.ForeignKey('respondents.id'), nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    completion_time_seconds = db.Column(db.Integer)  # Time taken to complete survey
    
    # Relationships
    answers = db.relationship('Answer', backref='survey_result', lazy=True)

class Answer(db.Model):
    __tablename__ = 'answers'
    
    id = db.Column(db.Integer, primary_key=True)
    survey_result_id = db.Column(db.Integer, db.ForeignKey('survey_results.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    question_option_id = db.Column(db.Integer, db.ForeignKey('question_options.id'), nullable=True)
    answer_text = db.Column(db.Text)  # For open-ended questions
    answer_numeric = db.Column(db.Float)  # For rating/numeric questions

# Data Processing Functions
class DataProcessor:
    @staticmethod
    def clean_excel_data(df):
        """Clean and standardize Excel data"""
        try:
            # Remove completely empty rows
            df = df.dropna(how='all')
            
            # Clean column names
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
            
            # Handle common data quality issues
            for col in df.columns:
                if df[col].dtype == 'object':
                    # Clean text fields
                    df[col] = df[col].astype(str).str.strip()
                    df[col] = df[col].replace(['nan', 'None', 'null', ''], None)
                
                # Convert date columns
                if 'date' in col.lower():
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                
                # Convert numeric columns
                if any(keyword in col.lower() for keyword in ['age', 'income', 'rating', 'score']):
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df, None
        except Exception as e:
            return None, str(e)
    
    @staticmethod
    def validate_survey_data(df):
        """Validate survey data structure"""
        required_columns = ['respondent_email', 'survey_title']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return False, f"Missing required columns: {missing_columns}"
        
        return True, None
    
    @staticmethod
    def process_survey_upload(df):
        """Process uploaded survey data and insert into database"""
        try:
            processed_count = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    # Process respondent
                    respondent = Respondent.query.filter_by(email=row['respondent_email']).first()
                    if not respondent:
                        respondent = Respondent(
                            email=row['respondent_email'],
                            age_group=row.get('age_group'),
                            gender=row.get('gender'),
                            location=row.get('location'),
                            income_level=row.get('income_level')
                        )
                        db.session.add(respondent)
                        db.session.flush()
                    
                    # Process survey
                    survey = Survey.query.filter_by(title=row['survey_title']).first()
                    if not survey:
                        survey = Survey(title=row['survey_title'])
                        db.session.add(survey)
                        db.session.flush()
                    
                    # Create survey result
                    survey_result = SurveyResult(
                        survey_id=survey.id,
                        respondent_id=respondent.id
                    )
                    db.session.add(survey_result)
                    db.session.flush()
                    
                    # Process answers (dynamic based on columns)
                    for col in df.columns:
                        if col not in ['respondent_email', 'survey_title', 'age_group', 'gender', 'location', 'income_level']:
                            # Create question if it doesn't exist
                            question = Question.query.filter_by(
                                survey_id=survey.id, 
                                question_text=col
                            ).first()
                            
                            if not question:
                                question = Question(
                                    survey_id=survey.id,
                                    question_text=col,
                                    question_type='text',
                                    order_num=len(survey.questions) + 1
                                )
                                db.session.add(question)
                                db.session.flush()
                            
                            # Create answer
                            if pd.notna(row[col]):
                                answer = Answer(
                                    survey_result_id=survey_result.id,
                                    question_id=question.id,
                                    answer_text=str(row[col])
                                )
                                db.session.add(answer)
                    
                    processed_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {index + 1}: {str(e)}")
            
            db.session.commit()
            return processed_count, errors
            
        except Exception as e:
            db.session.rollback()
            return 0, [str(e)]

# API Routes
@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload and process Excel files"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
            return jsonify({'error': 'Invalid file format. Please upload Excel or CSV files.'}), 400
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Read and process file
        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(filepath)
            else:
                df = pd.read_excel(filepath)
        except Exception as e:
            return jsonify({'error': f'Error reading file: {str(e)}'}), 400
        
        # Clean data
        df_clean, clean_error = DataProcessor.clean_excel_data(df)
        if clean_error:
            return jsonify({'error': f'Data cleaning error: {clean_error}'}), 400
        
        # Validate data
        is_valid, validation_error = DataProcessor.validate_survey_data(df_clean)
        if not is_valid:
            return jsonify({'error': validation_error}), 400
        
        # Process and insert data
        processed_count, errors = DataProcessor.process_survey_upload(df_clean)
        
        # Clean up uploaded file
        os.remove(filepath)
        
        response = {
            'message': f'Successfully processed {processed_count} records',
            'processed_count': processed_count,
            'total_rows': len(df_clean)
        }
        
        if errors:
            response['errors'] = errors[:10]  # Limit error messages
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/surveys', methods=['GET'])
def get_surveys():
    """Get all surveys with statistics"""
    try:
        surveys = db.session.query(
            Survey.id,
            Survey.title,
            Survey.version,
            Survey.status,
            Survey.created_at,
            func.count(SurveyResult.id).label('response_count')
        ).outerjoin(SurveyResult).group_by(Survey.id).all()
        
        result = []
        for survey in surveys:
            result.append({
                'id': survey.id,
                'title': survey.title,
                'version': survey.version,
                'status': survey.status,
                'created_at': survey.created_at.isoformat(),
                'response_count': survey.response_count
            })
        
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error fetching surveys: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/surveys/<int:survey_id>/responses', methods=['GET'])
def get_survey_responses(survey_id):
    """Get responses for a specific survey"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # Get survey responses with pagination
        responses = db.session.query(SurveyResult).filter_by(survey_id=survey_id).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        result = []
        for response in responses.items:
            respondent = response.respondent
            answers = {}
            
            for answer in response.answers:
                question_text = answer.question.question_text
                if answer.answer_text:
                    answers[question_text] = answer.answer_text
                elif answer.answer_numeric:
                    answers[question_text] = answer.answer_numeric
            
            result.append({
                'id': response.id,
                'completed_at': response.completed_at.isoformat(),
                'respondent': {
                    'email': respondent.email,
                    'age_group': respondent.age_group,
                    'gender': respondent.gender,
                    'location': respondent.location
                },
                'answers': answers
            })
        
        return jsonify({
            'responses': result,
            'pagination': {
                'page': responses.page,
                'pages': responses.pages,
                'per_page': responses.per_page,
                'total': responses.total
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching survey responses: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/analytics/demographics', methods=['GET'])
def get_demographics_analytics():
    """Get demographic analytics across all surveys"""
    try:
        # Age group distribution
        age_groups = db.session.query(
            Respondent.age_group,
            func.count(Respondent.id).label('count')
        ).group_by(Respondent.age_group).all()
        
        # Gender distribution
        gender_dist = db.session.query(
            Respondent.gender,
            func.count(Respondent.id).label('count')
        ).group_by(Respondent.gender).all()
        
        # Location distribution
        location_dist = db.session.query(
            Respondent.location,
            func.count(Respondent.id).label('count')
        ).group_by(Respondent.location).limit(10).all()
        
        result = {
            'age_groups': [{'group': ag.age_group, 'count': ag.count} for ag in age_groups],
            'gender_distribution': [{'gender': g.gender, 'count': g.count} for g in gender_dist],
            'top_locations': [{'location': l.location, 'count': l.count} for l in location_dist]
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error fetching demographics: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/analytics/trends', methods=['GET'])
def get_trends_analytics():
    """Get response trends over time"""
    try:
        # Response trends by day (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        trends = db.session.query(
            func.date(SurveyResult.completed_at).label('date'),
            func.count(SurveyResult.id).label('count')
        ).filter(
            SurveyResult.completed_at >= thirty_days_ago
        ).group_by(
            func.date(SurveyResult.completed_at)
        ).order_by('date').all()
        
        result = {
            'daily_responses': [
                {
                    'date': trend.date.isoformat(),
                    'count': trend.count
                } for trend in trends
            ]
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error fetching trends: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/export/<int:survey_id>', methods=['GET'])
def export_survey_data(survey_id):
    """Export survey data to Excel"""
    try:
        survey = Survey.query.get_or_404(survey_id)
        
        # Query all responses for the survey
        responses = db.session.query(SurveyResult).filter_by(survey_id=survey_id).all()
        
        if not responses:
            return jsonify({'error': 'No data to export'}), 404
        
        # Prepare data for export
        export_data = []
        for response in responses:
            row = {
                'response_id': response.id,
                'completed_at': response.completed_at,
                'respondent_email': response.respondent.email,
                'age_group': response.respondent.age_group,
                'gender': response.respondent.gender,
                'location': response.respondent.location
            }
            
            # Add answers
            for answer in response.answers:
                question_text = answer.question.question_text
                if answer.answer_text:
                    row[question_text] = answer.answer_text
                elif answer.answer_numeric:
                    row[question_text] = answer.answer_numeric
            
            export_data.append(row)
        
        # Create Excel file
        df = pd.DataFrame(export_data)
        
        # Create in-memory file
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Survey Data', index=False)
        
        output.seek(0)
        
        filename = f"{survey.title.replace(' ', '_')}_export_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        return jsonify({'error': 'Export failed'}), 500

@app.route('/api/stats', methods=['GET'])
def get_system_stats():
    """Get overall system statistics"""
    try:
        stats = {
            'total_surveys': Survey.query.count(),
            'total_responses': SurveyResult.query.count(),
            'total_respondents': Respondent.query.count(),
            'total_questions': Question.query.count(),
            'recent_uploads': SurveyResult.query.filter(
                SurveyResult.completed_at >= datetime.utcnow() - timedelta(days=7)
            ).count()
        }
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"Error fetching stats: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Initialize database
@app.before_first_request
def create_tables():
    """Create database tables if they don't exist"""
    try:
        db.create_all()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")

if __name__ == '__main__':
    # Create tables
    with app.app_context():
        db.create_all()
    
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=5000)