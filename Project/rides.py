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

@app.before_request
def add_c():
	if request.path.startswith('/api/v1/rides'):
		r = requests.post('http://18.233.82.73:80/api/v1/db/write', json={'table_name':'dummytride','db_action':'add','db_data':"dummy"})

#API to create a ride
@app.route('/api/v1/rides',methods = ["POST"])
def create_ride():
	#r = requests.post('http://18.233.82.73:80/api/v1/db/write', json={'table_name':'dummyt','db_action':'add','db_data':"dummy"})
	#Getting request body
	req=request.get_json()
	#Getting enum from constants file
	allplaces = placeList()
	avail = 0
	#Validating source and destination
	if int(req["source"]) in allplaces and int(req["destination"]) in allplaces:
		avail =1
	#Sending request to read, checking if user who is creating ride exists
	cheader = {"Origin":"34.201.40.30"}
	to_chk = requests.get('http://RideShare-1269314373.us-east-1.elb.amazonaws.com/api/v1/users',headers=cheader)
	#somelist = to_chk.text.strip('"][').split(', ')
	#somelist = json.loads(to_chk.text)
	if(to_chk.status_code!=204):
		somelist = json.loads(to_chk.text)
	else:
		return "User doesn't exist",400
	if((req["created_by"] in somelist) and avail == 1):
		#Sending request to write, adding new ride to Rides table
		r = requests.post('http://18.233.82.73:80/api/v1/db/write', json={'table_name':'Rides','db_action':'add','db_data':req})
		return {},201
	else:
		return "Invalid user/source or destination",400


#API to list details of ride
@app.route('/api/v1/rides/<rideid>',methods = ["GET"])
def ride_dets(rideid):
	#r = requests.post('http://18.233.82.73:80/api/v1/db/write', json={'table_name':'dummyt','db_action':'add','db_data':"dummy"})
	#Sending request to read, checking if given ride id is present
	to_chk = requests.post('http://18.233.82.73:80/api/v1/db/read', json={'table_name':'Rides','db_action':'list','db_data':rideid})
	if(json.loads(to_chk.text)['response']=="NA"):
		return "Ride not present",400
	return json.loads(to_chk.text)['response'],200


#API to list upcoming rides for a given source and destination
@app.route('/api/v1/rides',methods = ["GET"])
def list_rides():
	#r = requests.post('http://18.233.82.73:80/api/v1/db/write', json={'table_name':'dummyt','db_action':'add','db_data':"dummy"})
	#Getting enum from constants file
	allplaces = placeList()
	#extracting source and destination from url
	src = request.args.get("source")
	dst = request.args.get("destination")
	avail=0
	#Validating source and destination
	if int(src) in allplaces and int(dst) in allplaces:
		avail =1
	if avail==0:
		return "Invalid source/destination",400
	#obtaining current date-time
	current = datetime.now()
	cur_str = current.strftime("%d-%m-%Y:%S-%M-%H")
	cur_dt = datetime.strptime(cur_str,"%d-%m-%Y:%S-%M-%H")
 	#JSON of required data
	req = {
	"src" : int(src),
	"dst" : int(dst),
	"dtime" : cur_str
	}
	#Sending request to read, obtaining details of upcoming rides
	to_chk = requests.post("http://18.233.82.73:80/api/v1/db/read",json={'table_name':'Rides','db_action':'get','db_data':req})
	if(to_chk.text=='[]'):
		return {},200
	print(to_chk.text)
	return to_chk.text,200


#API to join a ride
@app.route('/api/v1/rides/<rideid>',methods = ["POST"])
def join_ride(rideid):
	#r = requests.post('http://18.233.82.73:80/api/v1/db/write', json={'table_name':'dummyt','db_action':'add','db_data':"dummy"})
	#getting request body
	req=request.get_json()
	#Sending request to read, checking if it is a valid ride id
	to_chkRide = requests.post('http://18.233.82.73:80/api/v1/db/read', json={'table_name':'Rides','db_action':'list','db_data':rideid})
	if(to_chkRide.text=="NA"):
		return "Ride not present",400
	#Sending request to read, checking if it is a valid username
	cheader = {"Origin":"52.6.169.242"}
	to_chkUser=requests.get('http://RideShare-1269314373.us-east-1.elb.amazonaws.com/api/v1/users',headers=cheader)
	print(to_chkUser.headers)
	somelist = json.loads(to_chkUser.text)
	if(req["username"] not in somelist):
		return "Invalid user",400
	#Sending request to write, adding user to corresponding ride
	add_req = requests.post('http://18.233.82.73:80/api/v1/db/write', json={'table_name':'Rides','db_action':'adduser','db_data':req["username"],'ridenum':rideid})
	return {},200


#API to delete a ride
@app.route('/api/v1/rides/<rideid>',methods = ["DELETE"])
def delete_ride(rideid):
	#r = requests.post('http://18.233.82.73:80/api/v1/db/write', json={'table_name':'dummyt','db_action':'add','db_data':"dummy"})
	#Sending request to read, checking if it is a valid ride id
	chk = requests.post('http://18.233.82.73:80/api/v1/db/read', json={'table_name':'Rides','db_action':'check','db_data':rideid})
	if(json.loads(chk.text)["response"]=="exists"):
		#Sending request to write, deleting corresponding ride
		r = requests.post('http://18.233.82.73:80/api/v1/db/write', json={'table_name':'Rides','db_action':'delete','db_data':rideid})
		return {},200
	else:
		return "ride does not exist",400

@app.route('/api/v1/rides/count',methods = ["GET"])
def count_rides():
	r = requests.post('http://18.233.82.73:80/api/v1/db/read',json={'table_name':'Rides','db_action':'count','db_data':'dummy'})
	return r.text,200
'''
@app.route('/api/v1/_count',methods = ["GET"])
def count_reqs():
	rows = db.session.query(dummyt).count()
	l=[]
	l.append(rows)
	return json.dumps(l),200

@app.route('/api/v1/_count',methods = ["DELETE"])
def reset_reqs():
	db.session.query(dummyt).delete()
	db.session.commit()
	return {},200
'''
@app.route('/api/v1/_count',methods = ["GET"])
def count_reqs():
        to_chk = requests.post('http://18.233.82.73:80/api/v1/db/read', json={'table_name':'dummytride','db_action':'count','db_data':"dummy"})
        return to_chk.text,200

@app.route('/api/v1/_count',methods = ["DELETE"])
def reset_reqs():
        to_chk = requests.post('http://18.233.82.73:80/api/v1/db/write', json={'table_name':'dummytride','db_action':'delete','db_data':"dummy"})
        return {},200



if __name__ == '__main__':
	app.run(debug = True,host='0.0.0.0')

