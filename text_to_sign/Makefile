# Compiler and flags
CXX = g++
CXXFLAGS = -pthread -Wall -std=c++11
LDFLAGS = -lGL -lGLEW -lglfw

all: server client renderer

server: server.cpp
	$(CXX) $(CXXFLAGS) server.cpp -o server

client: client.cpp
	$(CXX) $(CXXFLAGS) client.cpp -o client

renderer: renderer.cpp
	$(CXX) $(CXXFLAGS) renderer.cpp -o renderer $(LDFLAGS)

clean:
	rm -f server client renderer