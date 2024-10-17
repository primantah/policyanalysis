from flask import Flask, request, render_template, redirect, url_for
import os
import pdfplumber
import re

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max file size

ALLOWED_EXTENSIONS = {'txt', 'pdf'}

# Ensure the upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def read_text_from_file(file_path):
    # Check file extension
    _, file_extension = os.path.splitext(file_path)
    
    # Handle text files
    if file_extension.lower() == '.txt':
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                txt = file.read().strip()
            return txt
        except FileNotFoundError:
            return ""
        except UnicodeDecodeError:
            return ""
    
    # Handle PDF files
    elif file_extension.lower() == '.pdf':
        try:
            with pdfplumber.open(file_path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text()
            return text.strip() if text else "No text found in PDF."
        except Exception as e:
            return f"Error reading PDF: {str(e)}"
    
    return "Unsupported file type"

def check_words_in_text(txt, words_input):
    # Tokenize the text into words
    words_in_text = re.findall(r'\b\w+\b', txt)

    # Check if each word exists in the text
    results = {}
    for word in words_input.split(","):
        word = word.strip()
        
        # Check if the word is all uppercase
        if word.isupper():
            word_exists = any(w.upper() == word for w in words_in_text)  # Exact match, case-insensitive
        else:
            # Partial word match (for non-uppercase words), case-insensitive
            word_exists = any(w.lower().startswith(word.lower()) for w in words_in_text)

        if word_exists:
            results[word] = "exists"
        else:
            results[word] = "does not exist"

    # Sort results so that "exists" comes first
    sorted_results = sorted(results.items(), key=lambda item: item[1], reverse=True)
    return sorted_results

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':  # Handle POST request when the form is submitted
        results = []  # Initialize results as an empty list by default

        # Check if the post request has the file part
        if 'file' not in request.files:
            return redirect(request.url)
        
        file = request.files['file']
        keywords = request.form['keywords']
        
        if file.filename == '':
            return redirect(request.url)

        if not keywords.strip():
            return "Please enter at least one keyword to search."

        if file and allowed_file(file.filename):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            
            txt_content = read_text_from_file(file_path)
            
            if not txt_content:
                return "The uploaded file is empty. Please upload a valid file."
            
            results = check_words_in_text(txt_content, keywords)  # Process the results
            return render_template('results.html', results=results)  # Render results on POST request
        else:
            return "Unsupported file type. Please upload a text or PDF file."

    # If it's a GET request, show the upload form
    return render_template('upload.html')  # Render upload form on GET request


if __name__ == '__main__':
    app.run()
