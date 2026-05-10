import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

cred = credentials.Certificate('d2firebase-firebase-adminsdk-nea1t-ef16ff9cb9.json')
firebase_admin.initialize_app(cred)
db = firestore.client()
guilds_ref: firestore.firestore.CollectionGroup = db.collection(u'guilds')
