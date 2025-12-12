import uuid
import json
from dotenv import load_dotenv
import os
from fastapi import FastAPI, Request
from pydantic import BaseModel
import psycopg2
from datetime import datetime
import random
import uvicorn
import requests
from requests.auth import HTTPBasicAuth  # Add this import at the top
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Load environment variables from the .env file located in the parent folder of the parent folder of the parent folder
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "errorflow")
DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "pass")

K_USERNAME = os.getenv("KESTRA_USERNAME")
K_PASSWORD = os.getenv("KESTRA_PASSWORD")
K_BASE_URL = os.getenv("KESTRA_URL", "http://localhost:8080")
K_TENANT = os.getenv("KESTRA_TENANT", "main")
K_NAMESPACE = os.getenv("KESTRA_NAMESPACE", "main")
K_FLOW_ID = os.getenv("KESTRA_FLOW_ID", "error-intake")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


ERRORS = [
    {
        "service": "user-api",
        "error_type": "NullPointer",
        "message": "Cannot read property 'x' of null at UserController.java:42",
        "path": "/v1/users/123",
        "env": "prod",
    },
    {
        "service": "payment-api",
        "error_type": "Timeout",
        "message": "HTTP 504 while calling /charge on stripe-gateway, attempt=3",
        "path": "/v1/payments/charge",
        "env": "prod",
    },
    {
        "service": "order-api",
        "error_type": "DBError",
        "message": "org.postgresql.util.PSQLException: connection pool exhausted on orders_db",
        "path": "/v1/orders/checkout",
        "env": "prod",
    },
    {
        "service": "auth-service",
        "error_type": "ValidationError",
        "message": "JWT validation failed: token expired for user=42",
        "path": "/v1/auth/refresh",
        "env": "prod",
    },
    {
        "service": "api-gateway",
        "error_type": "RateLimitExceeded",
        "message": "429 Too Many Requests from client IP 192.168.1.1",
        "path": "/v1/resource",
        "env": "prod",
    },
    {
        "service": "payment-api",
        "error_type": "UpstreamError",
        "message": "HTTP 503 from stripe-gateway",
        "path": "/v1/payments/process",
        "env": "prod",
    },
    {
        "service": "order-api",
        "error_type": "ValidationError",
        "message": "JSONDecodeError: Missing required field 'order_id'",
        "path": "/v1/orders/create",
        "env": "prod",
    },
    {
        "service": "user-profile",
        "error_type": "Timeout",
        "message": "gRPC deadline exceeded calling profile-service",
        "path": "/v1/profiles/lookup",
        "env": "prod",
    }
]


# DB Connection
def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

@app.post("/errors/random")
async def produce_error():
    error = random.choice(ERRORS)
    error["timestamp"] = datetime.utcnow().isoformat()
    
    # Save to DB
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO errors (service, error_type, message, timestamp, env) VALUES (%s, %s, %s, %s, %s)",
        (error["service"], error["error_type"], error["message"], error["timestamp"], "prod")
    )
    conn.commit()
    cur.close()
    conn.close()
    
    return {"status": "error_logged", "error": error}

@app.post("/errors/with-kestra")
async def produce_error_kestra():
    error = random.choice(ERRORS)
    from datetime import datetime
    error["timestamp"] = datetime.utcnow().isoformat()

    # saave raw error to DB
    conn = get_db_connection()
    cur = conn.cursor()
    # cur.execute(
    #     "INSERT INTO errors (service, error_type, message, timestamp, env) VALUES (%s, %s, %s, %s, %s)",
    #     (error["service"], error["error_type"], error["message"], error["timestamp"], "prod")
    # )


    trace_id = str(uuid.uuid4())[:16]

    cur.execute(
        "INSERT INTO errors (service, error_type, message, timestamp, env, path, trace_id) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (error["service"], error["error_type"], error["message"], error["timestamp"], error["env"], error["path"], trace_id)
    )



    # update error_groups (simple grouping)
    cluster_key = f"{error['service']}:{error['error_type']}"

    # Try update existing group
    cur.execute(
        """
        UPDATE error_groups
        SET count = count + 1,
            last_seen = NOW(),
            status = 'OPEN'          -- if new error arrives, group becomes OPEN again
        WHERE cluster_key = %s
        RETURNING id;
        """,
        (cluster_key,)
    )

    row = cur.fetchone()
    if row is None:
        cur.execute(
            """
            INSERT INTO error_groups
            (cluster_key, service, error_type, title, summary, status, count, first_seen, last_seen)
            VALUES (%s, %s, %s, %s, %s, 'OPEN', 1, NOW(), NOW())
            RETURNING id;
            """,
            (
                cluster_key,
                error["service"],
                error["error_type"],
                f"{error['service']} - {error['error_type']}",
                f"Grouped errors for {error['service']} / {error['error_type']}",
            )
        )

    # group_id = row[0]
    conn.commit()
    cur.close()
    conn.close()


    # trigger Kestra
    url = f"{K_BASE_URL}/api/v1/{K_TENANT}/executions/{K_NAMESPACE}/{K_FLOW_ID}"
    files = {
        "error_event": (None, json.dumps(error), "application/json")
    }

    resp = requests.post(
        url,
        files=files,
        auth=HTTPBasicAuth(K_USERNAME, K_PASSWORD),
        timeout=10
    )

    return {
        "status": "error_logged_and_kestra_triggered",
        "error": error,
        "kestra_status": resp.status_code
    }



@app.post("/errors/custom")
async def ingest_custom_error(request: Request):
    """
    Real ingestion endpoint
    POST your own error JSON here instead of using the random generator
    Expected schema:
    {
      "service": "user-api",
      "error_type": "NullPointer",
      "message": "Cannot read property 'x' of null",
      "path": "/v1/users/123",
      "env": "prod"
    }
    """
    error = await request.json()

    # fill defaults
    error.setdefault("env", "prod")
    error.setdefault("path", "")
    error["timestamp"] = datetime.utcnow().isoformat()
    trace_id = str(uuid.uuid4())[:16]

    # ave raw error to DB
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO errors (service, error_type, message, timestamp, env, path, trace_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            error["service"],
            error["error_type"],
            error["message"],
            error["timestamp"],
            error["env"],
            error["path"],
            trace_id,
        ),
    )

    # update error_groups (same logic as random generator)
    cluster_key = f"{error['service']}:{error['error_type']}"

    cur.execute(
        """
        UPDATE error_groups
        SET count = count + 1,
            last_seen = NOW(),
            status = 'OPEN'
        WHERE cluster_key = %s
        RETURNING id;
        """,
        (cluster_key,),
    )

    row = cur.fetchone()
    if row is None:
        cur.execute(
            """
            INSERT INTO error_groups
            (cluster_key, service, error_type, title, summary, status, count, first_seen, last_seen)
            VALUES (%s, %s, %s, %s, %s, 'OPEN', 1, NOW(), NOW())
            RETURNING id;
            """,
            (
                cluster_key,
                error["service"],
                error["error_type"],
                f"{error['service']} - {error['error_type']}",
                f"Grouped errors for {error['service']} / {error['error_type']}",
            ),
        )

    conn.commit()
    cur.close()
    conn.close()

    # trigger Kestra (same as /errors/with-kestra)
    url = f"{K_BASE_URL}/api/v1/{K_TENANT}/executions/{K_NAMESPACE}/{K_FLOW_ID}"
    files = {
        "error_event": (None, json.dumps(error), "application/json")
    }

    resp = requests.post(
        url,
        files=files,
        auth=HTTPBasicAuth(K_USERNAME, K_PASSWORD),
        timeout=10,
    )

    return {
        "status": "custom_error_logged_and_kestra_triggered",
        "error": error,
        "kestra_status": resp.status_code,
    }



@app.post("/groups/{group_id}/resolve")
def resolve_group(group_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE error_groups
        SET status = 'RESOLVED',
            resolution_reason = 'manual',
            resolved_at = NOW()
        WHERE id = %s;
        """,
        (group_id,)
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"group_id": group_id, "status": "RESOLVED"}


@app.post("/groups/{cluster_key}/summarize")
def summarize_group(cluster_key: str):
    url = f"{K_BASE_URL}/api/v1/{K_TENANT}/executions/{K_NAMESPACE}/group-summary-agent"
    # inputs are sent as multipart; cluster_key is a STRING input
    files = {
        "cluster_key": (None, cluster_key),
    }
    resp = requests.post(
        url,
        files=files,
        auth=HTTPBasicAuth(K_USERNAME, K_PASSWORD),
        timeout=15,
    )
    return {
        "status": "kestra_triggered",
        "cluster_key": cluster_key,
        "kestra_status": resp.status_code,
        "kestra_body": resp.text,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
