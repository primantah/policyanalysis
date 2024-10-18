from flask import Flask, request, render_template, redirect, url_for
import os
import pdfplumber
import re

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max file size

ALLOWED_EXTENSIONS = {'txt', 'pdf'}

# Ensure the upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def read_text_from_file(file_path, first_page_in_pdf):
    # Check file extension
    _, file_extension = os.path.splitext(file_path)
    
    if file_extension.lower() == '.pdf':
        try:
            with pdfplumber.open(file_path) as pdf:
                text_by_page = {}
                full_text = ""
                page_offset = first_page_in_pdf - 1  # Adjust the page number according to the document
                
                for i, page in enumerate(pdf.pages, start=1):
                    # Extract text separately for left and right columns
                    left_text = page.within_bbox((0, 0, page.width / 2, page.height)).extract_text()
                    right_text = page.within_bbox((page.width / 2, 0, page.width, page.height)).extract_text()

                    combined_text = ""
                    if left_text:
                        combined_text += left_text + "\n"
                    if right_text:
                        combined_text += right_text + "\n"

                    if combined_text:
                        adjusted_page_num = i - page_offset
                        # Ensure the adjusted page number is not negative
                        if adjusted_page_num > 0:
                            text_by_page[adjusted_page_num] = combined_text
                            full_text += f"Page {adjusted_page_num}:\n{combined_text}\n\n"

            return {"full_text": full_text.strip(), "pages": text_by_page}
        except Exception as e:
            return {"full_text": f"Error reading PDF: {str(e)}", "pages": []}
    
    return {"full_text": "Unsupported file type", "pages": []}

def check_words_in_text(txt_data, words_input, first_page_in_pdf):
    full_text = txt_data['full_text']
    pages = txt_data['pages']

    # Tokenize the full text into words and split into sentences
    words_in_text = re.findall(r'\b\w+\b', full_text)

    # Check if each word exists in the text and on which page and the sentence
    results = {}
    for word in words_input.split(","):
        word = word.strip()
        word_info = {"exists": False, "pages": [], "sentences": {}}

        # Check in full text if the word exists
        if word.isupper():
            word_exists = any(w.upper() == word for w in words_in_text)  # Exact match, case-insensitive
        else:
            word_exists = any(w.lower().startswith(word.lower()) for w in words_in_text)  # Partial match

        if word_exists:
            word_info["exists"] = True

            # Now check which pages and sentences contain the word
            for page_num, page_text in pages.items():
                page_words = re.findall(r'\b\w+\b', page_text)
                if word.isupper():
                    page_word_exists = any(w.upper() == word for w in page_words)
                else:
                    page_word_exists = any(w.lower().startswith(word.lower()) for w in page_words)

                if page_word_exists:
                    word_info["pages"].append(page_num)

                    # Initialize sentences list for this page if not already created
                    if page_num not in word_info["sentences"]:
                        word_info["sentences"][page_num] = []

                    # Find sentences that contain the word on this page
                    for sentence in re.split(r'(?<=\.)\s+', page_text):
                        if word.lower() in sentence.lower():
                            word_info["sentences"][page_num].append(sentence.strip())

        results[word] = word_info

    # Sort results so that "exists" comes first
    sorted_results = sorted(results.items(), key=lambda item: item[1]["exists"], reverse=True)
    return sorted_results


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':  # Handle POST request
        # Check if the post request has the file part and required form data
        if 'file' not in request.files or request.files['file'].filename == '' or 'first_page' not in request.form or 'keywords' not in request.form:
            return redirect(request.url)  # Redirect back to the form if something is missing

        file = request.files['file']
        keywords = request.form['keywords']
        first_page_in_pdf = request.form.get('first_page', '')

        # Ensure first_page is a valid integer
        if not first_page_in_pdf.isdigit():
            return "Please enter a valid page number for the first page."

        first_page_in_pdf = int(first_page_in_pdf)

        if file and allowed_file(file.filename):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            
            txt_content = read_text_from_file(file_path, first_page_in_pdf)

            if not txt_content['full_text']:
                return "The uploaded file is empty. Please upload a valid file."

            # Pass the first_page_in_pdf value to the check_words_in_text function
            results = check_words_in_text(txt_content, keywords, first_page_in_pdf)  # Process the results
            return render_template('results.html', results=results)  # Render results on POST request

        else:
            return "Unsupported file type. Please upload a text or PDF file."
    
    # If it's a GET request, show the upload form
    return render_template('upload.html')  # Render upload form on GET request

if __name__ == '__main__':
    app.run()
