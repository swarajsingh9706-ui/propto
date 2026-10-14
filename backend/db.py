import os
from motor.motor_asyncio import AsyncIOMotorClient

mongo_url = os.environ['MONGO_URL']
# For MongoDB Atlas (TLS/SRV), pin the CA bundle via certifi. On some shared/cPanel
# hosts the default OpenSSL context fails the Atlas TLS handshake
# ([SSL: TLSV1_ALERT_INTERNAL_ERROR]); certifi's bundle resolves it. Local/plain
# connections (e.g. localhost) are unaffected.
_opts = {}
if "mongodb+srv" in mongo_url or "mongodb.net" in mongo_url:
    try:
        import certifi
        _opts["tlsCAFile"] = certifi.where()
    except Exception:
        pass
client = AsyncIOMotorClient(mongo_url, **_opts)
db = client[os.environ['DB_NAME']]

COMPLAINT_CATEGORIES = [
    "Plumbing", "Electrical", "Lift", "Security", "Housekeeping", "Civil",
    "Parking", "Gardening", "Water Supply", "DG Set", "Pest Control", "Pool AMC Vendor",
]
