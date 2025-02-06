from flask import Flask, render_template, jsonify
import logging
from utilities.logger import configure_logging
import threading
from main import run_pipeline
from datetime import datetime

app = Flask(__name__)
configure_logging()
logger = logging.getLogger(__name__)

# Store the last run time and status
last_run_time = None
is_running = False
last_run_status = None
last_run_results = None

@app.route('/')
def home():
    """Render the home page"""
    return render_template('index.html', 
                         last_run_time=last_run_time,
                         is_running=is_running,
                         last_run_status=last_run_status,
                         last_run_results=last_run_results)

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True) 