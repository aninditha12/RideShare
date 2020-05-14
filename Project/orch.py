from flask import Flask,request,jsonify
import json
import pika
import time
import os
import requests
import re
import threading
from random import seed
from random import randint
import uuid
import docker
import logging
from kazoo.client import KazooClient
from kazoo.client import KazooState

logging.basicConfig()

zk = KazooClient(hosts='zoo:2181')
zk.start()

prevl = 1
crash = "not_crashed"

#Watch that gets triggered whenever there are any changes in the slave nodes.
@zk.ChildrenWatch("/slave",send_event=True)
def keep_watching(children,event):
	client = docker.from_env()
	global prevl
	global crash
	#print(prevl)
	if(event==None):
		prevl = len(client.containers.list(filters={'name':'slave'}))
		print("inside the event none")
	l = len(client.containers.list(filters={'name':'slave'}))
	print("prev",prevl)
	print("currect",l)
	print("started watching.....")
	#children = zk.get_children("/slave")
	#print(children)
	flag = 0
	#In case a slave gets crashed not as a result of down scaling, new slave is created as a fault tolerance mechanism
	while(event!=None and prevl>l and crash=="crashed"):
		flag=1
		prevl = prevl-1
		strval = ''
		for i in range(3):
			value = randint(15,125)
			strval = strval + str(value)
		cname = "ubuntu_slave_"+strval
		c = client.containers.run(image="ubuntu_slave",command="python3 -E worker.py",environment = ["WORKER=slave"],volumes = {'ubuntu_workerdb': {'bind': '/code', 'mode': 'rw'}},network="ubuntu_default",links={"zookeeper":None},name=cname,detach=True)
		#print(c.logs())
		#time.sleep(10)
		children = zk.get_children("/slave")
		print("children created : ",children)
	if(crash == "crashed"):
		crash = "not_crashed"
	if(event!=None and flag==0):
		prevl = l
		children = zk.get_children("/slave")
		print("children not created",children,"prevl value",prevl)

app = Flask(__name__)

#Client class with method 'call' to send an RPC request and block until an answer is received when a read operation is performed.
class ReadRpcClient(object):

    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbit'))
        self.channel = self.connection.channel()

        result = self.channel.queue_declare(queue='responseq', durable=True)
        self.callback_queue = 'responseq'

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True)

    #Checks every response for its correlation_id and save it in self.response if it matches.
    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    #To send a callback queue address with the read request, in order to receive a response from the server.
    def call(self, n):
        print(type(n))
        self.response = None
        self.corr_id = str(uuid.uuid4())
        #Every RPC request has a seperate callback queue created based on the correlation_id property that is unique to every request.
        self.channel.basic_publish(
            exchange='',
            routing_key='readq',
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=n)
        while self.response is None:
            self.connection.process_data_events()
        self.connection.close()
        return self.response

#API to perform DB read operations
@app.route('/api/v1/db/read', methods=['POST'])
def db_read():
	new_json=request.get_json()
	if new_json["table_name"]!="reads" and new_json["table_name"]!="dummyt":
		r = requests.post('http://127.0.0.1:5000/api/v1/db/write',json={'table_name':'reads','db_action':'add','db_data':"dummy"})
	read_rpc = ReadRpcClient()
	resp = read_rpc.call(json.dumps(new_json))
	return resp

#API to perform DB write operations
@app.route('/api/v1/db/write', methods = ["POST"])
def db_write():
	new_json=request.get_json()
	connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbit'))
	channel = connection.channel()
	channel.queue_declare(queue='writeq', durable=True)

	#the message is published in the channel with the request json as the body
	channel.basic_publish(
	    exchange='',
	    routing_key='writeq',
	    body=json.dumps(new_json),
	    properties=pika.BasicProperties(
		delivery_mode=2,  # make message persistent
	    ))
	print("Sent message")
	connection.close()
	return "created",200

#function to identify the slave container with highest PID
def kill_container():
	client = docker.from_env()
	plist = []
	pdict = {}
	#filter 'name' used to identify slave containers.
	for container in client.containers.list(filters={"name":"slave"}):
		cidval = container.id
		inter = client.containers.get(cidval)
		pidval = inter.attrs['State']['Pid']
		plist.append(pidval)
		pdict[pidval] = cidval
	plist.sort(reverse=True)
	slavetokill = plist[0]
	slavetokill_cid = pdict[slavetokill]
	return slavetokill_cid,slavetokill

#API to crash slave container
@app.route('/api/v1/crash/slave',methods=['POST'])
def cr_slave():
	global crash
	crash = "crashed"
	client = docker.from_env()
	slavetokill_cid,slavetokill = kill_container()
	for container in client.containers.list(filters={"name":"slave"}):
		if(container.id == slavetokill_cid):
			container.kill()
			break
	return json.dumps([slavetokill]),200

#API to list worker container PIDs in ascending order
@app.route('/api/v1/worker/list',methods=['GET'])
def work_list():
	client = docker.from_env()
	a = []
	#filter 'name' used to identify slave and master containers.
	for container in client.containers.list(filters={'name':['slave','master']}):
		pval = client.containers.get(container.id)
		a.append(pval.attrs['State']['Pid'])
	a.sort()
	return json.dumps(a),200

#API to clear Users and Rides data from the database
@app.route('/api/v1/db/clear',methods = ['POST'])
def clear_db():
	to_chk = requests.post('http://127.0.0.1:5000/api/v1/db/write',json = {'table_name':'all','db_action':'clear','db_data':"nada"})
	return {},200

#Function that gets called when the first request is sent to the orchestrator.
@app.before_first_request
def activate_check():
	#Function to decide the scaling required, based on the number of read requests recorded in last 2 minutes.
	#Based on the required scale, additional slave containers are either created or a few slaves are killed. 
	def check_req():
		#to obtain the number of read request in last 2 minutes from the reads table
		r = requests.post('http://127.0.0.1:5000/api/v1/db/read',json={'table_name':'reads','db_action':'count','db_data':"dummy"})
		print("The number of requests : ",r.text)
		req_cnt = int(r.text[1:-1])
		#to calculate the scaling required
		if req_cnt%20 != 0 or req_cnt==0:
			print(req_cnt/20)
			scale = int(req_cnt/20) +1
		else:
			scale = int(req_cnt/20)
		ids = requests.get('http://127.0.0.1:5000/api/v1/worker/list')
		cur_scale = len(json.loads(ids.text))-1
		client = docker.from_env()
		#In case up-scaling is required
		if cur_scale<scale:
			for i in range(scale-cur_scale):
				cmd = "python3 -E worker.py"
				stval = ''
				for i in range(3):
					value = randint(10, 100)
					stval = stval + str(value)
				#To start a new container with 'slave' in the name, yet unique.
				cname = "ubuntu_slave_" + stval
				#Docker sdk containers method to run a new container using existing slave image and rest of the parametes as specified.
				client.containers.run("ubuntu_slave", cmd, network = "ubuntu_default",volumes = {'ubuntu_workerdb': {'bind': '/code', 'mode': 'rw'}}, environment = ["WORKER=slave"], name = cname,links={"zookeeper":None},detach = True)
				print("Created")
		#In case down-scaling is required
		elif cur_scale>scale:
			for i in range(cur_scale-scale):
				#To kill the container with highest PID
				slavetokill_cid,slavetokill = kill_container()
				for container in client.containers.list(filters={"name":"slave"}):
					if(container.id == slavetokill_cid):
						container.kill()
						break
				print("Crashed")
		print(time.strftime("%I:%M:%S %p")+" scale: "+ str(scale) )
		#At the end of every 2 minutes, the past reads count is cleared.
		to_chk = requests.post('http://127.0.0.1:5000/api/v1/db/write', json={'table_name':'reads','db_action':'delete','db_data':"dummy"})
		print("deleted all the requests")
	#This function is made to run in parallel on a seperate thread, and sleep function is used to run the above function every 2 minutes.
	def run_check():
		while True:
			print("starting 2 minutes")
			check_req()
			time.sleep(120)
			print("End of 2 minutes")
	thread = threading.Thread(target=run_check)
	thread.start()


if __name__ == '__main__':
	app.run(debug = True,host='0.0.0.0', use_reloader=False)

#zk.stop()
