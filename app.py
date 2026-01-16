from flask import Flask, render_template, request, jsonify, send_file, session
import google.generativeai as genai
import os
from datetime import datetime
import json
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = 'resume_builder_secret'  

# Configure Gemini API
GEMINI_API_KEY = 'AIzaSyAtYMBk3N8ApEkk0ZnxuHwSaZy9TN_EMoU'  
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/select-experience')
def select_experience():
    return render_template('select_experience.html')

@app.route('/student-check', methods=['POST'])
def student_check():
    data = request.json
    experience = data.get('experience')
    session['experience'] = experience
    
    if experience in ['no_experience', 'less_than_3']:
        return jsonify({'show_student_question': True})
    return jsonify({'show_student_question': False, 'redirect': '/templates'})

@app.route('/student-qualification', methods=['POST'])
def student_qualification():
    data = request.json
    is_student = data.get('is_student')
    qualification = data.get('qualification')
    
    session['is_student'] = is_student
    session['qualification'] = qualification
    
    return jsonify({'redirect': '/templates'})

@app.route('/templates')
def templates():
    experience = session.get('experience', 'no_experience')
    return render_template('templates.html', experience=experience)

@app.route('/fill-information')
def fill_information():
    template_id = request.args.get('template_id', 'template1')
    session['template_id'] = template_id
    return render_template('fill_information.html')

@app.route('/save-section', methods=['POST'])
def save_section():
    data = request.json
    section = data.get('section')
    content = data.get('content')
    
    if 'resume_data' not in session:
        session['resume_data'] = {}
    
    session['resume_data'][section] = content
    session.modified = True
    
    # Calculate completeness
    total_sections = 6
    completed_sections = len(session['resume_data'])
    completeness = (completed_sections / total_sections) * 100
    
    return jsonify({'success': True, 'completeness': completeness})

@app.route('/generate-job-description', methods=['POST'])
def generate_job_description():
    data = request.json
    experience_data = data.get('experience')
    
    prompt = f"""
    Create a professional job description based on the following information:
    Position: {experience_data.get('position')}
    Company: {experience_data.get('company')}
    Duration: {experience_data.get('start_date')} to {experience_data.get('end_date')}
    Location: {experience_data.get('location')}
    
    Generate 4-5 bullet points describing key responsibilities and achievements.
    Make it professional and impactful. 
    Do not overwrite.
    Make it very short within 20 to 30 words. 
    do not write the position, company, duration, location in output
    """
    
    try:
        response = model.generate_content(prompt)
        description = response.text
        return jsonify({'success': True, 'description': description})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/generate-summary', methods=['POST'])
def generate_summary():
    resume_data = session.get('resume_data', {})
    
    prompt = f"""
    Create a professional resume summary based on the following information:
    
    Personal Info: {json.dumps(resume_data.get('heading', {}))}
    Education: {json.dumps(resume_data.get('education', []))}
    Experience: {json.dumps(resume_data.get('experience', []))}
    Skills: {json.dumps(resume_data.get('skills', []))}
    
    Generate a compelling 3-4 sentence professional summary that highlights the candidate's strengths,
    experience, and career objectives.
    It should be simple in humanly language. 
    Please do consider the available data and if any one of them is empty then give the summary on the basis of available data.
    """
    print("RESUME DATA:", resume_data)

    
    try:
        response = model.generate_content(prompt)
        summary = response.text
        return jsonify({'success': True, 'summary': summary})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/suggest-skills', methods=['POST'])
def suggest_skills():
    data = request.json
    experience = data.get('experience', [])
    
    prompt = f"""
    Based on the following work experience, suggest 8-10 relevant professional skills:
    {json.dumps(experience)}
    
    Return only the skill names, one per line.
    """
    
    try:
        response = model.generate_content(prompt)
        skills = response.text.strip().split('\n')
        return jsonify({'success': True, 'skills': [s.strip('- ').strip() for s in skills if s.strip()]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/spell-check', methods=['POST'])
def spell_check():
    data = request.json
    text_to_check = data.get('text', '')
    
    if not text_to_check or len(text_to_check.strip()) < 2:
        return jsonify({'success': True, 'corrected_text': text_to_check})

    prompt = f"""
    You are a professional editor. Please check the following text for spelling and grammatical errors.
    If there are errors, provide the corrected version.
    If there are no errors, return the original text exactly as it is.
    Return ONLY the corrected text without any explanations or introductory remarks.
    
    Text: {text_to_check}
    """
    
    try:
        response = model.generate_content(prompt)
        corrected_text = response.text.strip()
        return jsonify({
            'success': True, 
            'corrected_text': corrected_text
        })
    except Exception as e:
        print(f"Spell check error: {e}")
        return jsonify({'success': False, 'error': str(e)})
        
@app.route('/preview-resume')
def preview_resume():
    # Retrieve the saved data from the session
    resume_data = session.get('resume_data', {})
    template_id = session.get('template_id', 'template1')
    
    # Render the preview page with the actual data
    return render_template('preview_resume.html', 
                           resume_data=resume_data, 
                           template_id=template_id)

@app.route('/download-pdf')
def download_pdf():
    resume_data = session.get('resume_data', {})
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Add content to PDF (simplified version)
    if 'heading' in resume_data:
        heading = resume_data['heading']
        title = Paragraph(f"{heading.get('first_name', '')} {heading.get('last_name', '')}", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 12))
    
    doc.build(story)
    buffer.seek(0)
    
    return send_file(buffer, as_attachment=True, download_name='resume.pdf', mimetype='application/pdf')

@app.route('/analyze-resume')
def analyze_resume():

    return render_template('analyze_resume.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'resume_file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'})
    
    file = request.files['resume_file']
    # Here you would extract text from the resume file
    
    prompt = """
    Analyze this resume and provide:
    1. Overall score (out of 10)
    2. Strengths (3-4 points)
    3. Areas for improvement (3-4 points)
    4. Keyword optimization suggestions
    5. Formatting feedback
    """
    
    try:
        response = model.generate_content(prompt)
        analysis = response.text
        return jsonify({'success': True, 'analysis': analysis})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)

