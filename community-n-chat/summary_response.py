from flask import Flask, request, jsonify
import os
from groq import Groq

app = Flask(__name__)

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY)

@app.route('/summarize', methods=['POST'])
def summarize():
    messages = request.json['messages']
    chat_content = "\n".join([f"{m['sender']}: {m['content']}" for m in messages])
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes chat conversations. Make sure to identify the language first and after analysing only provide the summary in the native language. And only provide summary nothing else. If the language is native but written in english, provide the answer in english but with words of native language"},
                {"role": "user", "content": f"Please summarize the following chat conversation:\n\n{chat_content}"}
            ],
            model="llama-3.1-70b-versatile",
        )
        
        summary = chat_completion.choices[0].message.content
        return jsonify({"summary": summary})
    except Exception as e:
        print(f"Error calling Groq API: {str(e)}")
        return jsonify({"error": "Failed to generate summary"}), 500

if __name__ == '__main__':
    app.run(debug=True,port = 4001)
