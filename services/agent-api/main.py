# from flask import Flask, request, jsonify
# from oumi_agent import process_error

# app = Flask(__name__)

# @app.route('/process-error', methods=['POST'])
# def process_error_endpoint():
#     data = request.get_json()
#     error = data.get('error')
#     result = process_error(error)
#     return jsonify(result)

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5001)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
import os
import requests
import uvicorn

app = FastAPI()

DB_DSN = "dbname=errorflow user=user password=pass host=localhost"
OUMI_INFER_URL = os.getenv("OUMI_INFER_URL", "http://localhost:8009/infer")  # adjust to your Oumi endpoint

class SummarizeRequest(BaseModel):
    cluster_key: str

# def get_db():
#     return psycopg2.connect(DB_DSN)

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="errorflow",
        user="user",
        password="pass"
    )

@app.post("/summarize-group")
def summarize_group(body: SummarizeRequest):
    # conn = get_db()
    conn= get_db_connection()
    cur = conn.cursor()

    # 1. Fetch group
    cur.execute(
        "SELECT id, service, error_type, count FROM error_groups WHERE cluster_key = %s",
        (body.cluster_key,)
    )
    row = cur.fetchone()
    if row is None:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Group not found")
    group_id, service, error_type, count = row

    # 2. Fetch recent errors for this group
    cur.execute(
        """
        SELECT message, timestamp
        FROM errors
        WHERE service = %s AND error_type = %s
        ORDER BY timestamp DESC
        LIMIT 20
        """,
        (service, error_type)
    )
    errors = cur.fetchall()

    if not errors:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="No errors for this group")

    error_snippets = [
        f"- [{t}] {m}" for (m, t) in errors
    ]
    context = "\n".join(error_snippets)

    # 3. Call Oumi (dummy example: simple REST LLM wrapper)
    prompt = (
        f"You are an SRE assistant.\n"
        f"Service: {service}\n"
        f"Error type: {error_type}\n"
        f"Total occurrences (approx): {count}\n\n"
        f"Recent error messages:\n{context}\n\n"
        f"Please return:\n"
        f"1. A short title for this error group.\n"
        f"2. A 3-4 sentence summary of likely cause / impact.\n"
        f"3. 3 concrete next steps for an engineer.\n"
    )

    # Replace with real Oumi call; here assume a generic LLM endpoint
    resp = requests.post(
        OUMI_INFER_URL,
        json={"prompt": prompt},
        timeout=30
    )
    resp.raise_for_status()
    text = resp.json().get("text", "").strip()

    # Very simple parsing: first line as title, rest as summary
    lines = text.splitlines()
    title = lines[0][:190] if lines else f"{service} - {error_type}"
    summary = "\n".join(lines[1:]) if len(lines) > 1 else text

    # 4. Store back into DB
    cur.execute(
        """
        UPDATE error_groups
        SET title = %s,
            summary = %s
        WHERE id = %s
        """,
        (title, summary, group_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    return {
        "group_id": group_id,
        "cluster_key": body.cluster_key,
        "title": title,
        "summary": summary,
    }


# Example curl request for the /summarize-group API
# Replace <cluster_key_value> with the actual cluster key value

# curl -X POST \
#      -H "Content-Type: application/json" \
#      -d '{"cluster_key": "<cluster_key_value>"}' \
#      http://localhost:8009/summarize-group


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8009)
