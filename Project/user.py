from flask import Flask,request,jsonify
import json
import requests
import re
from datetime import datetime
from placesEnum import placeList
import ast
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'

db = SQLAlchemy(app)

@app.route('/api/v1/db/clear',methods = ["POST"])
def clear_db():
	db.session.query(User).delete()
	db.session.commit()
	return {},200

@app.before_request
def add_cnt():
	if request.path.startswith('/api/v1/users'):
		r = requests.post('http://18.233.82.73:80/api/v1/db/write', json={'table_name':'dummytuser','db_action':'add','db_data':"dummy"})

#API to create new user
@app.route('/api/v1/users',methods = ["PUT"])
def add_user():

	#Getting request body
	req=request.get_json()
	#Sending request to read to check if username exits
	to_chk = requests.post('http://18.233.82.73:80/api/v1/db/read', json={'table_name':'User','db_action':'check','db_data':req["username"]})
	#validating SHA password
	passd_val=re.match("^[a-fA-F0-9]{40}$",req["password"])
	if(json.loads(to_chk.text)["response"]=="exists"):
		return "Username already exists", 400
	elif(passd_val==None):
		return "Invalid password", 400
	else:
		#Sending request to write to add user to DB
		r = requests.post('http://18.233.82.73:80/api/v1/db/write', json={'table_name':'User','db_action':'add','db_data':request.json})
		return {},201


#API to delete user
@app.route('/api/v1/users/<name>',methods = ["DELETE"])
def remove_user(name):
	#r = requests.post('http://127.0.0.1:5000/api/v1/db/write', json={'table_name':'dummyt','db_action':'add','db_data':"dummy"})
	#Sending request to read to check if user exits
	to_chk = requests.post('http://18.233.82.73:80/api/v1/db/read', json={'table_name':'User','db_action':'check','db_data':name})
	if(json.loads(to_chk.text)["response"]=="exists"):
		#Sending request to write, removing user from Users table
		r = requests.post('http://18.233.82.73:80/api/v1/db/write', json={'table_name':'User','db_action':'delete','db_data':name})

		r4 = requests.post('http://18.233.82.73:80/api/v1/db/write', json={'table_name':'Rides','db_action':'ridescreatedbyuser','db_data':name})
		#Sending request to read, getting all rides that user is part of
		r2 = requests.post('http://18.233.82.73:80/api/v1/db/read', json={'table_name':'Rides','db_action':'rideswithuser','db_data':name})
		#Sending request to write, deleting user from the corresponding rides
		r3 = requests.post('http://18.233.82.73:80/api/v1/db/write', json={'table_name':'Rides','db_action':'rideswithuser','db_data':r2.text,'username':name})
		return {},200
	else:
		return "user does not exist",400


@app.route('/api/v1/users',methods = ["GET"])
def list_user():
	#r = requests.post('http://127.0.0.1:5000/api/v1/db/write', json={'table_name':'dummyt','db_action':'add','db_data':"dummy"})
	to_chk = requests.post('http://18.233.82.73:80/api/v1/db/read', json={'table_name':'User','db_action':'list','db_data':''})
	if(to_chk.text=='[]'):
		return {},204
	return to_chk.text,200

@app.route('/api/v1/_count',methods = ["GET"])
def count_reqs():
	to_chk = requests.post('http://18.233.82.73:80/api/v1/db/read', json={'table_name':'dummytuser','db_action':'count','db_data':"dummy"})
	return to_chk.text,200

@app.route('/api/v1/_count',methods = ["DELETE"])
def reset_reqs():
	to_chk = requests.post('http://18.233.82.73:80/api/v1/db/write', json={'table_name':'dummytuser','db_action':'delete','db_data':"dummy"})
	return {},200

if __name__ == '__main__':
	app.run(debug = True,host='0.0.0.0')
