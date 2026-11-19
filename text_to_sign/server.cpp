#include <iostream>
#include <string>
#include <thread>
#include <vector>
#include <cstring>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <mutex>
#include <algorithm>

#define PORT 8080
#define BUFFER_SIZE 1024

std::vector<int> active_clients;
std::mutex clients_mutex;

// Safely broadcast to all active clients
void broadcast_message(int sender_socket, const std::string& message) {
    std::lock_guard<std::mutex> lock(clients_mutex);
    for (int client_sock : active_clients) {
        if (client_sock != sender_socket) {
            // MSG_NOSIGNAL prevents the server from crashing if a client abruptly closed
            send(client_sock, message.c_str(), message.length(), MSG_NOSIGNAL);
        }
    }
}

void handle_client(int client_socket) {
    char buffer[BUFFER_SIZE];
    
    std::cout << "[SERVER] New client connected. Socket: " << client_socket << std::endl;

    while (true) {
        memset(buffer, 0, BUFFER_SIZE);
        int bytes_read = read(client_socket, buffer, BUFFER_SIZE);
        
        if (bytes_read <= 0) {
            std::cout << "[SERVER] Client " << client_socket << " disconnected." << std::endl;
            
            // Safely remove this client from the active list
            std::lock_guard<std::mutex> lock(clients_mutex);
            active_clients.erase(std::remove(active_clients.begin(), active_clients.end(), client_socket), active_clients.end());
            
            close(client_socket);
            break;
        }

        std::string msg(buffer);
        std::cout << "[SERVER] Routing message from " << client_socket << ": " << msg << std::endl;

        // Route the raw text to other clients
        broadcast_message(client_socket, msg);
    }
}

int main() {
    int server_fd, client_socket;
    struct sockaddr_in address;
    int opt = 1;
    int addrlen = sizeof(address);

    if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) == 0) {
        perror("Socket failed"); exit(EXIT_FAILURE);
    }
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(PORT);

    if (bind(server_fd, (struct sockaddr *)&address, sizeof(address)) < 0) {
        perror("Bind failed"); exit(EXIT_FAILURE);
    }
    
    listen(server_fd, 3);

    std::cout << "[SERVER] Listening on port " << PORT << "..." << std::endl;

    while (true) {
        client_socket = accept(server_fd, (struct sockaddr *)&address, (socklen_t*)&addrlen);
        
        {
            std::lock_guard<std::mutex> lock(clients_mutex);
            active_clients.push_back(client_socket);
        }
        
        std::thread(handle_client, client_socket).detach();
    }
    return 0;
}