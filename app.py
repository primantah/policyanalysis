from flask import Flask, request, render_template, redirect, url_for
import pdfplumber
import re

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max file size

ALLOWED_EXTENSIONS = {'txt', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def read_text_from_file(file):
    # Check file extension
    file_extension = file.filename.rsplit('.', 1)[1].lower()

    if file_extension == 'pdf':
        try:
            with pdfplumber.open(file) as pdf:
                text_by_page = {}
                full_text = ""

                for i, page in enumerate(pdf.pages, start=1):
                    combined_text = page.extract_text() or "No text found on this page."
                    text_by_page[i] = combined_text
                    full_text += f"Page {i}:\n{combined_text}\n\n"

            return {"full_text": full_text.strip(), "pages": text_by_page}
        except Exception as e:
            return {"full_text": f"Error reading PDF: {str(e)}", "pages": []}

    return {"full_text": "Unsupported file type", "pages": []}

def check_words_in_text(txt_data, words_input):
    full_text = txt_data['full_text']
    pages = txt_data['pages']
    words_in_text = re.findall(r'\b\w+\b', full_text)
    results = {}

    for word in words_input.split(","):
        word = word.strip()
        word_info = {"exists": False, "pages": []}

        word_exists = any(word.lower() in w.lower() for w in words_in_text)

        if word_exists:
            word_info["exists"] = True
            for page_num, page_text in pages.items():
                page_words = re.findall(r'\b\w+\b', page_text)
                if any(word.lower() in w.lower() for w in page_words):
                    word_info["pages"].append(page_num)

        results[word] = word_info

    sorted_results = sorted(results.items(), key=lambda item: item[1]["exists"], reverse=True)
    return sorted_results

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files or request.files['file'].filename == '' or 'keywords' not in request.form:
            return redirect(request.url)

        file = request.files['file']
        keywords = request.form['keywords']

        if file and allowed_file(file.filename):
            txt_content = read_text_from_file(file)

            if not txt_content['full_text']:
                return "The uploaded file is empty. Please upload a valid file."

            results = check_words_in_text(txt_content, keywords)
            return render_template('results.html', results=results)

        else:
            return "Unsupported file type. Please upload a text or PDF file."
    
    return render_template('upload.html')

if __name__ == '__main__':
    app.run()
