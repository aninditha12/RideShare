import os
from sqlalchemy import Column, Integer, String
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import requests
import re
import json
from datetime import datetime
from placesEnum import placeList
import pika
from random import seed
from random import randint
import logging
from kazoo.client import KazooClient
from kazoo.client import KazooState
import subprocess
import docker

#get environment variable
worker = os.environ['WORKER']

if(worker=="slave"):
	#zookeeper functionality to associate znode with a slave 
	logging.basicConfig()
	zk = KazooClient(hosts='zoo:2181')
	zk.start()
	#zk.delete("/slave",recursive=True)
	zk.ensure_path("/slave")
	s = "/slave/node_"+str(randint(15,125))
	if zk.exists(s):
		print("slave node1 already present")
	else:
		print(s)
		zk.create(s,b"slave node1",ephemeral=True)
		#zk.create(s+"pooj",b"",ephemeral=True)
		print("Node created - slave container")

engine = create_engine('sqlite:///data.db', echo = True)
Base = declarative_base()

#class for user table
class User(Base):
	__tablename__ = 'User'
	id = Column(Integer,primary_key = True)
	username = Column(String(800),nullable = False)
	password = Column(String(800),nullable=False)

	def __init__(self,username,password):
		self.username = username
		self.password = password


#class for rides table
class Rides(Base):
	__tablename__ = 'Rides'

	rideid = Column(Integer,primary_key = True)
	created_by = Column(String(800), nullable = False)
	timestamp = Column(String(800), nullable = False)
	source = Column(Integer,nullable = False)
	destination = Column(Integer,nullable =False)
	#string containing semicolon seperated usernames part of the ride
	users = Column(String(7000))

	def __init__(self,created_by,timestamp,source,destination,users=""):
		self.created_by = created_by
		self.timestamp = timestamp
		self.source = source
		self.destination = destination
		self.users = users

class dummyt(Base):
	__tablename__ = 'dummyt'
	sid = Column(Integer,primary_key = True)
	stxt = Column(String(800),nullable = False)

	def __init__(self,stxt):
		self.stxt = stxt

#class for table to count read requests
class reads(Base):
	__tablename__ = 'reads'
	sid = Column(Integer,primary_key = True)
	stxt = Column(String(800),nullable = False)

	def __init__(self,stxt):
		self.stxt = stxt


Base.metadata.create_all(engine)
Session = sessionmaker(bind = engine)
session = Session()

#function to write to the database
def write_ops(body):
	#extract request body
	new_json=json.loads(body)
	table_name = new_json['table_name']
	db_action = new_json['db_action']
	db_data = new_json['db_data']

	if table_name == "all":
			session.query(Rides).delete()
			session.query(User).delete()
			session.commit()

	if table_name == "Rides":
		if db_action == "add":
			created_by = db_data['created_by']
			timestamp = db_data['timestamp']
			source = db_data['source']
			destination = db_data['destination']
			#creating an instance of class rides
			new_action = Rides(created_by,timestamp,source,destination,created_by)
			session.add(new_action)
			session.commit()
			#return "created", 201

		elif db_action == "delete":
			session.query(Rides).filter(Rides.rideid == db_data).delete()
			session.commit()
			#return "deleted",200

		elif db_action == "adduser":
			newride = new_json['ridenum']
			session.query(Rides).filter(Rides.rideid==newride).update({Rides.users:Rides.users+";"+db_data}, synchronize_session = False)
			session.commit()
			#return {},200

		elif db_action == "rideswithuser":
			res = json.loads(db_data)
			#extracting username from json body
			uname=new_json['username']
			sepval=';'
			#iterating through list of rideIds user is a part of
			for i in res:
				#Extracting row from the table with corresponding rideid
				rec=session.query(Rides).filter(Rides.rideid==i)
				#splitting string based on ;
				userlist=str(rec[0].users).split(";")
				#If empty, continue with the next iteration
				if userlist==['']:
					continue
				#remove username from the list
				userlist.remove(uname)
				#join list elements into ; seperated string
				strvalue=sepval.join(userlist)
				#update the row values
				session.query(Rides).filter(Rides.rideid==i).update({Rides.users:strvalue}, synchronize_session = False)
				session.commit()
			#return {},200

		elif db_action == "ridescreatedbyuser":
			session.query(Rides).filter(Rides.created_by == db_data).delete()
			session.commit()
			#return "deleted",200

	elif table_name == "dummyt":
		if db_action == "add":
			val = "dummy"
			new_action = dummyt(val)
			session.add(new_action)
			session.commit()
			#return "created",201
		if db_action == "delete":
			session.query(dummyt).delete()
			session.commit()

	elif table_name == "reads":
		if db_action == "add":
			val = "dummy"
			new_action = reads(val)
			session.add(new_action)
			session.commit()
			#return "created",201
		if db_action == "delete":
			session.query(reads).delete()
			session.commit()

	elif table_name == "User":
		if db_action == "add":
			print(db_data)
			name = db_data['username']
			password = db_data['password']
			#creating an instance of class user
			new_action = User(name,password)
			session.add(new_action)
			session.commit()
			#return "created",201

		elif db_action == "delete":
			session.query(User).filter(User.username == db_data).delete()
			session.commit()
			#return "deleted",200

#function to read from database
def read_ops(body):
	new_json=json.loads(body)
	print(new_json)
	table_name = new_json['table_name']
	db_action = new_json['db_action']
	db_data = new_json['db_data']

	res_json = {}

	if table_name == "User":
		if db_action == "check":
			records = session.query(User).filter(User.username == db_data).all()
			if(records!=[]):
				res_json["response"]="exists"
				return json.dumps(res_json)
			else:
				res_json["response"]="does not exist"
				return json.dumps(res_json)
		if db_action == "list":
			records = session.query(User.username).all()
			a = []
			for i in records:
				a.append(i[0])
			return json.dumps(a)
	elif table_name=="dummyt":
		if db_action=="count":
			rows = session.query(dummyt).count()
			l=[]
			l.append(rows)
			return json.dumps(l)

	elif table_name=="reads":
		if db_action=="count":
			rows = session.query(reads).count()
			l=[]
			l.append(rows)
			return json.dumps(l)

	elif table_name=="Rides":
		if db_action=="list":
			records = session.query(Rides).filter(Rides.rideid == db_data).all()
			if(records!=[]):
				a={"rideId":str(records[0].rideid),"Created_by":str(records[0].created_by),"Timestamp":str(records[0].timestamp),"users":str(records[0].users).split(";"),"Source":str(records[0].source),"Destination":str(records[0].destination)}
				#converting to JSON
				res_json["response"]=a
				return json.dumps(res_json)
			else:
				res_json["response"]="NA"
				return json.dumps(res_json)

		elif db_action == "check":
			records = session.query(Rides).filter(Rides.rideid == db_data).all()
			if(records!=[]):
				res_json["response"]="exists"
				return json.dumps(res_json)
			else:
				res_json["response"]="Does not exist"
				return json.dumps(res_json)

		elif db_action == "get":
			records = session.query(Rides).filter(Rides.source == db_data["src"]).all()
			up_rides = []
			for r in records:
				if(datetime.strptime(r.timestamp,"%d-%m-%Y:%S-%M-%H")< datetime.strptime(db_data["dtime"],"%d-%m-%Y:%S-%M-%H")):
					continue
				if(r.destination != db_data["dst"]):
					continue
				rd = {"rideId": r.rideid, "username": r.created_by, "timestamp": r.timestamp}
				up_rides.append(rd)
			#converting to JSON
			return json.dumps(up_rides)

		elif db_action == "rideswithuser":
			a=[]
			records = session.query(Rides)
			for r in records:
				rlist=str(r.users).split(";")
				if db_data in rlist:
					a.append(r.rideid)
			#converting to JSON
			return json.dumps(a)


#function to send sync data to sync queue
def send_sync(mbody):
	#create connection
	connection1 = pika.BlockingConnection(pika.ConnectionParameters(host='rabbit'))
	#establish channel
	channel1 = connection1.channel()
	#Create a direct exchange
	channel1.exchange_declare(exchange='sync', exchange_type='direct')
	#finding out pid associated with each container
	client = docker.from_env()
	plist=[]
	pdict={}
	for container in client.containers.list(filters={"name":"slave"}):
		cidval = container.id
		inter = client.containers.get(cidval)
		pidval = inter.attrs['State']['Pid']
		plist.append(pidval)
		pdict[pidval] = cidval
	#sorting list if PIDs in ascending order
	plist.sort()
	slavetokill = plist[0]
	slavetokill_cid = pdict[slavetokill]
	idkanymore = slavetokill_cid[:12]
	#publish message to the exchange with routing key as the lowest pid
	channel1.basic_publish(exchange='sync', routing_key=idkanymore, body=mbody)
	print("Sent message")
	connection1.close()

#function to complete write operation and send ack
def callback1(ch, method, properties, body):
	write_ops(body)
	print("Done")
	send_sync(body)
	ch.basic_ack(delivery_tag=method.delivery_tag)

#function to complete write operation and send response to response queue
def callback2(ch, method, properties, body):
	response = read_ops(body)
	#publish message to response queue
	ch.basic_publish(exchange='', routing_key=properties.reply_to, properties = pika.BasicProperties(correlation_id = properties.correlation_id), body=str(response))
	ch.basic_ack(delivery_tag=method.delivery_tag)

#function to perform write operation
def callback3(ch, method, properties, body):
	write_ops(body)


if(worker=="master"):
	#create connection
	connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbit'))
	#establish channel
	channel = connection.channel()

	#Write queue
	channel.queue_declare(queue='writeq', durable=True)
	print(' [*] Waiting for messages. To exit press CTRL+C')
	channel.basic_qos(prefetch_count=1)
	#consume data to be written from queue, callback1 is called
	channel.basic_consume(queue='writeq', on_message_callback=callback1)

	channel.start_consuming()



if(worker == "slave"):
	#create connection
	connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbit'))
	#establish channel
	channel = connection.channel()

	#sync queue
	channel.exchange_declare(exchange='sync', exchange_type='direct')
	result = channel.queue_declare(queue='', exclusive=True)
	queue_name = result.method.queue
	#find out pid of current container
	severe = subprocess.check_output(["cat","/etc/hostname"],universal_newlines=True)
	s = severe.strip()
	#receive message from exchange based on pid
	channel.queue_bind(exchange='sync', queue=queue_name,routing_key=s)

	print(' [*] Waiting for sync. To exit press CTRL+C')

	channel.basic_consume(queue=queue_name, on_message_callback=callback3, auto_ack=True)

	#read queue
	channel.queue_declare(queue='readq')

	channel.basic_qos(prefetch_count=1)
	print(' [*] Waiting for messages. To exit press CTRL+C')
	#consume data to be read from queue, callback2 is called
	channel.basic_consume(queue='readq', on_message_callback=callback2)
	#print("done callback")
	channel.start_consuming()

