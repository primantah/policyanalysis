from flask import Flask, request, render_template, redirect, url_for
import pdfplumber
import re
import openai  # GPT API integration
from dotenv import load_dotenv
import os

# Initialize Flask app
app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max file size

ALLOWED_EXTENSIONS = {'pdf'}

# Load API Key from .env
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

print(f"API Key: {openai.api_key}")  # Check if the key is loaded correctly

if not openai.api_key:
    raise ValueError("OpenAI API Key not found! Set it in .env or environment variables.")

def allowed_file(filename):
    """ Check if the file is a PDF """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def read_text_from_file(file):
    """ Extracts text from a PDF file """
    try:
        with pdfplumber.open(file) as pdf:
            text_by_page = {}
            full_text = ""

            for i, page in enumerate(pdf.pages, start=1):
                combined_text = page.extract_text()
                if combined_text:  # Store only non-empty pages
                    text_by_page[i] = combined_text
                    full_text += f"Page {i}:\n{combined_text}\n\n"

        return {"full_text": full_text.strip(), "pages": text_by_page}
    except Exception as e:
        return {"full_text": f"Error reading PDF: {str(e)}", "pages": {}}

def classify_sentence_with_gpt(sentence):
    """ Uses GPT API to classify if a sentence is health-related """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"Does the following sentence discuss a topic directly related to health or climate? Answer 'Yes' or 'No'.\n\nSentence: {sentence}"}
            ],
            max_tokens=5,
            temperature=0
        )
        classification = response['choices'][0]['message']['content'].strip()
        return classification.lower() == "yes"
    except Exception as e:
        print(f"Error with GPT API: {e}")
        return False

def check_words_in_text(txt_data, words_input, use_smart_search=False):
    """ Searches for keywords and optionally classifies sentences contextually """
    full_text = txt_data['full_text']
    pages = txt_data['pages']
    results = {}

    for word in words_input.split(","):
        word = word.strip()
        word_info = {"exists": False, "pages": [], "sentences": {}}

        if word.lower() in full_text.lower():
            word_info["exists"] = True

            for page_num, page_text in pages.items():
                if word.lower() in page_text.lower():
                    word_info["pages"].append(page_num)

                    relevant_sentences = [
                        sentence.strip()
                        for sentence in re.split(r'(?<=\.)\s+', page_text)
                        if word.lower() in sentence.lower()
                    ]

                    classified_sentences = []
                    for sentence in relevant_sentences:
                        if use_smart_search:
                            is_health_related = classify_sentence_with_gpt(sentence)
                        else:
                            is_health_related = True  # Assume true for regular search
                        classified_sentences.append(
                            {"text": sentence, "is_related": is_health_related}
                        )

                    word_info["sentences"][page_num] = classified_sentences

        results[word] = word_info

    return sorted(results.items(), key=lambda item: item[1]["exists"], reverse=True)

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files or request.files['file'].filename == '' or 'keywords' not in request.form:
            return redirect(request.url)

        file = request.files['file']
        keywords = request.form['keywords']
        search_mode = request.form.get("search_mode", "regular")

        if not allowed_file(file.filename):
            return "Error: Only PDF files are allowed."

        # Check file size
        file.seek(0, os.SEEK_END)
        if file.tell() > app.config['MAX_CONTENT_LENGTH']:
            return "File too large. Maximum allowed size is 16MB."
        file.seek(0)

        try:
            txt_content = read_text_from_file(file)
        except Exception as e:
            return f"Error processing file: {e}"

        if not txt_content['full_text']:
            return "The uploaded file is empty. Please upload a valid PDF."

        use_smart_search = search_mode == "smart"
        results = check_words_in_text(txt_content, keywords, use_smart_search)

        return render_template('results.html', results=results, use_smart_search=use_smart_search)

    return render_template('upload.html')

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=False)
