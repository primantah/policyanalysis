from flask import Flask, request, render_template, redirect, url_for
import pdfplumber
import re
import unicodedata

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

# Normalize text for Unicode consistency
def normalize_text(text):
    return unicodedata.normalize('NFKC', text)

# Remove diacritical marks from Arabic text
def remove_diacritics(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

def check_words_in_text(txt_data, words_input):
    full_text = txt_data['full_text']
    pages = txt_data['pages']

    # Match both Arabic and Latin alphabet words
    words_in_text = re.findall(r'[\w\u0600-\u06FF]+', full_text)

    # Split input on both commas and slashes, normalize, and remove empty strings
    keywords = re.split(r'[,/]', words_input)
    keywords = [normalize_text(word.strip()) for word in keywords if word.strip()]  # Normalize input

    results = {}
    for word in keywords:
        word_info = {"exists": False, "pages": []}

        # Remove diacritics for comparison
        word_clean = remove_diacritics(word)
        word_exists = any(word_clean in remove_diacritics(w) for w in words_in_text)

        if word_exists:
            word_info["exists"] = True
            for page_num, page_text in pages.items():
                # Match both Arabic and Latin words in the current page
                page_words = re.findall(r'[\w\u0600-\u06FF]+', page_text)
                if any(word_clean in remove_diacritics(w) for w in page_words):
                    word_info["pages"].append(page_num)

        results[word] = word_info

    # Sort results so that existing words come first
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
