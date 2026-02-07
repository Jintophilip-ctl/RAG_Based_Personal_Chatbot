#!/rag-chatbot/rag-env/bin/python3 
import sys 
import shutil
import stat
import os

from flask import Flask, render_template, request, session

sys.path.append('/rag-chatbot/scripts') 
from rag_engine_with_history import build_qa_chain, append_memory

FAMILY_FILE = "/rag-chatbot/docs/family.txt"
PERSIST_DIR = "/rag-chatbot/chroma_db"

app = Flask(__name__, template_folder= "/rag-chatbot/web/templates")

app.secret_key = "family-assistant-secret"  # required for session

# Build RAG once at startup
qa_chain = build_qa_chain()
@app.route("/", methods=["GET", "POST"])
def index():
    if "chat" not in session:
        session["chat"] = []
    if request.method == "POST":
        question = request.form.get("question")
        #for debug
        #print(question)
        if question:
            # 🧠 REMEMBER MODE
            if question.lower().startswith("remember:"):
                memory_text = question[len("remember:"):].strip()
                #formating datat for Better chunking
                structured_text = (
                   "Family Update:\n"
                   f"{memory_text.rstrip('.') }."
                )
                # 1. Save to family.txt
                append_memory(structured_text, FAMILY_FILE)
                # 2  Remember input in  current chat 
                qa_chain.memory.chat_memory.add_ai_message(
                        f"Remember this fact for future questions: {memory_text}"
                )
                answer = "Got it 👍 I've remembered that. The update will be available after the application restarts."
            else:    
                result = qa_chain.invoke({"question": question})
                answer = result["answer"]
            #for debug
            #print (answer)
            session["chat"].append({
                "question": question,
                "answer": answer
            })
            session.modified = True

    return render_template(
        "index.html",
        chat=session["chat"]
    )

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
