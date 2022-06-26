import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import threading

cred = credentials.Certificate('d2firebase-firebase-adminsdk-nea1t-ef16ff9cb9.json')
firebase_admin.initialize_app(cred)
db = firestore.client()
users_ref: firestore.firestore.CollectionGroup = db.collection(u'users')
guilds_ref: firestore.firestore.CollectionGroup = db.collection(u'guilds')
events_ref: firestore.firestore.CollectionGroup = db.collection(u'events')
