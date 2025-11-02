import firebase_admin
from firebase_admin import credentials, firestore
import asyncio
import os

DB_CLIENT = None

def init_db():
    global DB_CLIENT
    try:
        cred_path = '.gitignore/firebase_creds.json'
        if not os.path.exists(cred_path):
            raise FileNotFoundError(f"'{cred_path}' not found. Please download it from your Firebase project settings.")
            
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        DB_CLIENT = firestore.client()
        print("Firebase connection established.")
    except Exception as e:
        print(f"Failed to initialize Firebase: {e}")
        exit()

# --- Internal BLOCKING functions ---

def _update_message_count_sync(user_id, server_id):
    doc_ref = DB_CLIENT.collection("users").document(str(user_id))
    doc_ref.set({
        "server_id": str(server_id),
        "message_count": firestore.Increment(1)
    }, merge=True)

def _get_user_profile_sync(user_id):
    doc_ref = DB_CLIENT.collection("users").document(str(user_id))
    doc = doc_ref.get()
    return doc.to_dict() if doc.exists else None

def _set_user_motto_sync(user_id, server_id, motto):
    doc_ref = DB_CLIENT.collection("users").document(str(user_id))
    doc_ref.set({
        "server_id": str(server_id),
        "user_mmotto": motto
    }, merge=True)

# --- ANALYSIS FUNCTION ---
@firestore.transactional
def _update_user_analysis_sync(transaction, doc_ref, new_scores: dict):
    """
    (Blocking & Transactional)
    Safely reads, calculates, and writes new average analysis scores.
    """
    snapshot = doc_ref.get(transaction=transaction)
    
    if snapshot.exists:
        data = snapshot.to_dict()
        current_avg = data.get("analysis_scores", {})
        total_analyzed = data.get("total_analyzed", 0)
    else:
        current_avg = {}
        total_analyzed = 0

    # Get all 5 scores, defaulting to 0
    avg_agitation = current_avg.get("agitation", 0)
    avg_dissent = current_avg.get("dissent", 0)
    avg_compliance = current_avg.get("compliance", 0)
    avg_sophistication = current_avg.get("sophistication", 0) 
    avg_positivity = current_avg.get("positivity", 0)       
    
    # Calculate new averages
    new_avg_agitation = ((avg_agitation * total_analyzed) + new_scores.get("agitation", 0)) / (total_analyzed + 1)
    new_avg_dissent = ((avg_dissent * total_analyzed) + new_scores.get("dissent", 0)) / (total_analyzed + 1)
    new_avg_compliance = ((avg_compliance * total_analyzed) + new_scores.get("compliance", 0)) / (total_analyzed + 1)
    new_avg_sophistication = ((avg_sophistication * total_analyzed) + new_scores.get("sophistication", 0)) / (total_analyzed + 1) # NEW
    new_avg_positivity = ((avg_positivity * total_analyzed) + new_scores.get("positivity", 0)) / (total_analyzed + 1)       # NEW
    
    # Prepare data to write
    new_data = {
        "analysis_scores": {
            "agitation": new_avg_agitation,
            "dissent": new_avg_dissent,
            "compliance": new_avg_compliance,
            "sophistication": new_avg_sophistication, 
            "positivity": new_avg_positivity      
        },
        "total_analyzed": total_analyzed + 1,
        "last_analyzed_ts": firestore.SERVER_TIMESTAMP
    }
    
    transaction.set(doc_ref, new_data, merge=True)


# --- Public ASYNC functions ---

async def update_message_count(user_id, server_id):
    await asyncio.to_thread(_update_message_count_sync, user_id, server_id)

async def get_user_profile(user_id):
    return await asyncio.to_thread(_get_user_profile_sync, user_id)

async def set_user_motto(user_id, server_id, motto):
    await asyncio.to_thread(_set_user_motto_sync, user_id, server_id, motto)

async def update_user_analysis(user_id: int, new_scores: dict):
    doc_ref = DB_CLIENT.collection("users").document(str(user_id))
    transaction = DB_CLIENT.transaction()
    await asyncio.to_thread(_update_user_analysis_sync, transaction, doc_ref, new_scores)