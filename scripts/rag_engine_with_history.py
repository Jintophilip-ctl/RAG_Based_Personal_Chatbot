#!/rag-chatbot/rag-env/bin/python3
import gc
import hashlib
import os
import shutil


from langchain.chains import ConversationalRetrievalChain
from langchain.chains import RetrievalQA
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate

from langchain_community.document_loaders import TextLoader
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain_community.vectorstores import Chroma

from langchain_text_splitters import RecursiveCharacterTextSplitter


PERSIST_DIR = "/rag-chatbot/chroma_db"
HASH_FILE =  "/rag-chatbot/docs/data.hash"
DOC_PATH = "/rag-chatbot/docs/family.txt"
qa_chain = None  



def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def needs_reindex(doc_path, hash_file):
    current_hash = file_hash(doc_path)

    if not os.path.exists(hash_file):
        return True, current_hash

    with open(hash_file, "r") as f:
        stored_hash = f.read().strip()

    return current_hash != stored_hash, current_hash



def build_qa_chain():
    reindex, current_hash = needs_reindex(DOC_PATH, HASH_FILE)

    embeddings = OllamaEmbeddings(model="nomic-embed-text")

    if reindex:
        print("🔄 Document changed → rebuilding Chroma index")

        # Delete old DB safely
        if os.path.exists(PERSIST_DIR):
            shutil.rmtree(PERSIST_DIR)

        # Load & split
        loader = TextLoader(DOC_PATH)
        documents = loader.load()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100
        )
        chunks = splitter.split_documents(documents)

        # Build new DB
        vectorstore = Chroma.from_documents(
            chunks,
            embedding=embeddings,
            persist_directory=PERSIST_DIR
        )

        # Save hash
        with open(HASH_FILE, "w") as f:
            f.write(current_hash)

    else:
        print("✅ No document change → using existing Chroma DB")

        vectorstore = Chroma(
            persist_directory=PERSIST_DIR,
            embedding_function=embeddings
        )

    # Prompt 
    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template="""
You are answering questions about a fictional family.
Use ONLY the information in the context.
You may combine facts from multiple parts of the context.
If the answer cannot be determined from the context, reply exactly:
"I don't know."

Context:
{context}

Question:
{question}

Answer:
"""
    )

    prompt1 = PromptTemplate(
        input_variables=["context", "question"],
        template="""
You are answering questions about a family.
Use ONLY the information in the context.
You may combine facts from multiple parts of the context.
Do NOT explain your reasoning.
Do NOT show steps.
Do NOT add extra information.
If the answer cannot be determined from the context, reply exactly:
"I don't know."

Context:
{context}

Question:
{question}

Answer:
"""
    )

    # Memory
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
        output_key="answer"
    )

    llm = Ollama(model="phi", temperature=0)

    qa = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 4, "fetch_k": 8, "lambda_mult": 0.8}
        ),
        memory=memory,
        combine_docs_chain_kwargs={"prompt": prompt},
        return_source_documents=True
    )
    # This code is for debugging purpose to see What retrived form doc 
    #docs = vectorstore.similarity_search("Who are Mark's family members?", k=7)
    #print("RETRIEVED DOCS:")
    #for i, d in enumerate(docs, 1):
    #   print(f"\n--- Doc {i} ---")
    #   print(d.page_content)

    return qa


#def safe_rebuild():
 #   global qa_chain

 #   print("🔄 Rebuilding vector index safely...")

    # 1. Drop old chain
   # gc.collect()
  #  qa_chain = None

    # 2. Remove old Chroma DB
 #   shutil.rmtree(PERSIST_DIR, ignore_errors=True)
  #  os.makedirs(PERSIST_DIR, exist_ok=True)

    # 3. Rebuild
 #   qa_chain = build_qa_chain()

  #  print("✅ Rebuild complete")
  #  return qa_chain


def append_memory(text, path="/rag-chatbot/docs/family.txt"):
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + text.strip() + "\n")


if __name__ == "__main__":
    #for testing 
    qa = build_qa_chain()

    r1 = qa.invoke({"question": "Who are Mark's family members?"})
    print(r1["answer"])

    r2 = qa.invoke({"question": "When is Emily’s next appointment?"})
    print(r2["answer"])
