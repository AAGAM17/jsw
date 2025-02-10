from flask import Flask, render_template, jsonify, request, url_for, redirect
import logging
from utilities.logger import configure_logging
import threading
from main import run_pipeline
from datetime import datetime, timedelta
from scrapers.perplexity_client import PerplexityClient
import os
from dotenv import load_dotenv

app = Flask(__name__)
configure_logging()
logger = logging.getLogger(__name__)
load_dotenv()

# Store the last run time and status
last_run_time = None
is_running = False
last_run_status = None
last_run_results = None

# Initialize Perplexity client
perplexity_client = PerplexityClient()

# Store project data and chat contexts
project_data = {}
chat_contexts = {}

# In-memory storage for projects (replace with database in production)
projects = []

@app.route('/')
def index():
    """Home page with run button"""
    return render_template('index.html', 
                         last_run_time=last_run_time,
                         is_running=is_running,
                         last_run_status=last_run_status,
                         last_run_results=last_run_results)

@app.route('/chat')
def chat_interface():
    """Chat interface for project discovery"""
    return render_template('chat.html')

@app.route('/projects')
def projects_list():
    # Get filter parameters
    project_type = request.args.get('type')
    value_range = request.args.get('value')
    timeline = request.args.get('timeline')
    sort_by = request.args.get('sort')
    
    filtered_projects = projects.copy()
    
    # Apply filters
    if project_type:
        filtered_projects = [p for p in filtered_projects if p['type'] == project_type]
        
    if value_range:
        min_val, max_val = map(float, value_range.split('-'))
        filtered_projects = [p for p in filtered_projects if min_val <= p['value'] <= max_val]
        
    if timeline:
        months = int(timeline.split('-')[0])
        cutoff_date = datetime.now() + timedelta(days=30*months)
        filtered_projects = [p for p in filtered_projects if p['start_date'] <= cutoff_date]
    
    # Apply sorting
    if sort_by:
        reverse = sort_by.endswith('-desc')
        key = sort_by.split('-')[0]
        filtered_projects.sort(key=lambda x: x[key], reverse=reverse)
    
    return render_template('projects.html', projects=filtered_projects)

@app.route('/project/<project_id>')
def project_details(project_id):
    # Find project by ID (company_title)
    project = next((p for p in projects if f"{p['company']}_{p['title'].lower().replace(' ', '_')}" == project_id), None)
    
    if not project:
        return "Project not found", 404
        
    return render_template('project_details.html', project=project)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    project_id = data.get('project_id')
    message = data.get('message')
    
    # If no project_id, this is a general chat
    if not project_id:
        response = perplexity_client.get_project_info(message)
        return jsonify({"response": response})
    
    # Find project context
    project = next((p for p in projects if f"{p['company']}_{p['title'].lower().replace(' ', '_')}" == project_id), None)
    
    if not project:
        return jsonify({"error": "Project not found"}), 404
    
    # Create context for the AI
    context = f"""
    Project: {project['title']}
    Company: {project['company']}
    Value: ₹{project['value']} Crore
    Timeline: {project['start_date'].strftime('%B %d, %Y')} to {project['end_date'].strftime('%B %d, %Y')}
    Description: {project['description']}
    Source: {project['source_url']}
    """
    
    # Get AI response using Perplexity
    response = perplexity_client.get_project_info(context + "\n\nUser question: " + message)
    return jsonify({"response": response})

@app.route('/api/projects', methods=['POST'])
def update_projects():
    """Update projects data from the pipeline"""
    data = request.json
    if not isinstance(data, list):
        return jsonify({"error": "Expected a list of projects"}), 400
        
    # Convert string dates to datetime objects
    for project in data:
        project['start_date'] = datetime.strptime(project['start_date'], '%Y-%m-%d')
        project['end_date'] = datetime.strptime(project['end_date'], '%Y-%m-%d')
    
    # Update global projects list
    global projects
    projects = data
    
    return jsonify({"message": "Projects updated successfully", "count": len(projects)})

@app.route('/run', methods=['POST'])
def run_script():
    """Endpoint to trigger the main script"""
    global is_running, last_run_time, last_run_status, last_run_results
    
    if is_running:
        return jsonify({
            'status': 'error',
            'message': 'Script is already running'
        }), 400
    
    def run_task():
        global is_running, last_run_time, last_run_status, last_run_results
        try:
            is_running = True
            last_run_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            last_run_status = 'running'
            last_run_results = None
            
            # Run the pipeline
            run_pipeline()
            
            last_run_status = 'completed'
            last_run_results = 'Pipeline completed successfully'
            
        except Exception as e:
            logger.error(f"Error running pipeline: {str(e)}", exc_info=True)
            last_run_status = 'failed'
            last_run_results = f"Error: {str(e)}"
            
        finally:
            is_running = False
    
    # Start the task in a background thread
    thread = threading.Thread(target=run_task)
    thread.start()
    
    return jsonify({
        'status': 'success',
        'message': 'Script started successfully'
    })

@app.route('/status')
def get_status():
    """Get the current status of the script"""
    return jsonify({
        'is_running': is_running,
        'last_run_time': last_run_time,
        'status': last_run_status,
        'results': last_run_results
    })

@app.route('/api/project/<project_id>')
def get_project_info(project_id):
    """Get project information for the chat interface"""
    # This is test data - in production, you would fetch this from your database
    test_projects = {
        'larsen_toubro_mumbai_metro_project': {
            'company': 'Larsen & Toubro',
            'title': 'Mumbai Metro Project',
            'value': 500.0,
            'steel_requirement': 400,
            'timeline': 'Q3, 2024 - 3 years',
            'contacts': [
                {
                    'name': 'Ashish Raheja',
                    'role': 'VP, Eng. Procurement',
                    'phone': '+91 9898439394',
                    'email': 'ashish.raheja@rahee.com'
                },
                {
                    'name': 'Boman Irani',
                    'role': 'Senior VP, Procurement',
                    'phone': '+91 9074598939',
                    'email': 'boman.irani@rahee.com'
                }
            ]
        },
        'rahee_infra_delhi_viaduct': {
            'company': 'Rahee Infratech',
            'title': 'Delhi Metro Viaduct Construction',
            'value': 350.0,
            'steel_requirement': 280,
            'timeline': 'Q4, 2024 - 2 years',
            'contacts': [
                {
                    'name': 'Rajesh Kumar',
                    'role': 'Project Director',
                    'phone': '+91 9876543210',
                    'email': 'rajesh.kumar@rahee.com'
                }
            ]
        }
    }
    
    # Get project info or return default test data
    project_info = test_projects.get(project_id, {
        'company': project_id.replace('_', ' ').title(),
        'title': 'Test Project',
        'value': 100.0,
        'steel_requirement': 80,
        'timeline': 'Q1, 2024 - 1 year'
    })
    
    return jsonify(project_info)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True) 