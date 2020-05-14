# RideShare
RideShare is an application that can be used to pool rides. It is a cloud based application deployed on Amazon Web Services. New users can join with the help of a unique name and password. Users can create a ride between a source and destination. Other users can join this ride. DBaaS is also implemented to provide a fault tolerant, highly available database as a service for the RideShare application.
<br>
<br>
Flask is used for the backend. Various REST APIs are used to serve different endpoints. Functions performed by them include create user, create ride, list upcoming rides between source and destination, join a ride, delete User and delete Ride. Two microservices are used - one catering to the user management, and another catering to the ride management. They are present in two different EC2 instances in AWS. An AWS Application Load Balancer is used which distributes incoming HTTP requests to one of the two EC2 instances based on the URL route of the request. 
<br>
<br>
For the DBaaS, a database orchestrator engine is implemented. It listens to incoming HTTP
requests from users and rides microservices and performs the database read and write
According to the request. The orchestrator is also implemented using flask. RabbitMq is used as a message broker. There are two types of workers - master and slave. The master serves all write requests while the slave serves read requests. The master and each slave are run in their own containers. The master and the slaves each have their own DB.
<br><br>
Four queues are used. 
#### Write Queue
The orchestrator pushes all the write requests it receives into the Write Queue. The master listens to the Write Queue. It picks up incoming messages and writes them to a persistent database. Once the request is completed, the master pushes the request into the Sync Queue<br>
#### Read Queue and Response Queue<br>
The orchestrator pushes all the read requests it receives into the Read Queue and waits for a response. It listens to the Response Queue for the same. All the slaves listen to the Read Queue. The tasks are distributed among the slaves in a round robin manner. A slave picks up the message, queries the database based on the request and pushes the output to the Response Queue<br>
#### Sync Queue<br>
This queue is used to maintain consistency between the master and slave DBs. It is implemented using a Direct Exchange. The master pushes the serviced write request it receives from the Write Queue to the Sync Queue with the routing key as the lowest PID among slave workers. All slave workers listen to the Sync Queue with their PIDs as the routing key value. The message is delivered to the corresponding slave based on the routing key, which then updates the database.<br>
<br>
<br>
Scalability is provided to ensure that read requests can be served without much delay. Every two minutes, based on the number of HTTP requests received by the orchestrator, the number of slaves are increased/decreased. If the count is between 0 to 20, one slave container is running;  If the count is between 21 to 40, two slave containers are running and so on.
<br>
<br>
Zookeeper is used to provide High Availability. Each slave has a znode associated with it and the zookeeper keeps a watch on these slaves. In case a slave crashes, a new one is started. All the data is copied to the new slave. 
<br>
<br>
# Instructions to run
In users instance, the following commands are used to create and run the user container<br>
```
docker build -t users:latest .
docker run -i -p 80:5000 --name users -d users
```
In rides instance, the following commands are used to create and run the user container<br>
```
docker build -t rides:latest .
docker run -i -p 80:5000 --name users -d rides
```
In the DBaaS instance, the following command is used to start all the containers<br>
`docker compose up --build`
<br>
<br>
Requests can then be sent in postman to the respective instances to perform the required tasks.




