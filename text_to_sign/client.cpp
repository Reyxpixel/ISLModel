#include <iostream>
#include <string>
#include <cstring>
#include <thread>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <fcntl.h>

#define PORT 8080
#define BUFFER_SIZE 1024

int user_type = 2; // Default to Normal User
int renderer_pipe = -1;
pid_t renderer_pid = -1;
// Client-side NLP processing
std::string run_nlp_pipeline(const std::string& input_sentence) {
    std::string result = "";
    std::string command = "python3 nlp_tool.py \"" + input_sentence + "\"";
    
    char buffer[128];
    FILE* pipe = popen(command.c_str(), "r");
    if (!pipe) return "ERROR: Failed to run local NLP tool.";
    
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        result += buffer;
    }
    pclose(pipe);
    
    if (!result.empty() && result.back() == '\n') result.pop_back();
    return result;
}

void start_renderer()
{
    int pipefd[2];

    if (pipe(pipefd) == -1)
    {
        perror("pipe");
        exit(EXIT_FAILURE);
    }

    renderer_pid = fork();

    if (renderer_pid == -1)
    {
        perror("fork");
        exit(EXIT_FAILURE);
    }

    if (renderer_pid == 0)
    {
        // Child process

        close(pipefd[1]);                // Close write end

        dup2(pipefd[0], STDIN_FILENO);   // Pipe becomes stdin

        close(pipefd[0]);

        execl("./renderer", "./renderer", NULL);

        perror("Failed to start renderer");
        exit(EXIT_FAILURE);
    }

    // Parent process

    close(pipefd[0]);       // Close read end

    renderer_pipe = pipefd[1];
}
// Thread to continuously listen for messages from the server
void receive_messages(int sock) {
    char buffer[BUFFER_SIZE];
    while (true) {
        memset(buffer, 0, BUFFER_SIZE);
        int bytes_read = read(sock, buffer, BUFFER_SIZE);
        if (bytes_read <= 0) {
            std::cout << "\n[Disconnected from server]" << std::endl;
            exit(0);
        }

        std::string incoming_msg(buffer);

        // If this client is the Disabled user, translate incoming English to ISL
        if (user_type == 1)
        {
            std::string isl_gloss = run_nlp_pipeline(incoming_msg);

            // Print English message
            std::cout << "\n=============================\n";
            std::cout << "Incoming English : " << incoming_msg << std::endl;
            std::cout << "Converted Gloss  : " << isl_gloss << std::endl;
            std::cout << "=============================\n";

            // Send to renderer
            std::string renderer_input = isl_gloss + "\n";

            write(renderer_pipe,
                renderer_input.c_str(),
                renderer_input.size());

            std::cout << "You: " << std::flush;
        }
        else
        {
            std::cout << "\n[Incoming]: "
                    << incoming_msg
                    << "\nYou: "
                    << std::flush;
        }
    }
}

int main() {
    int sock = 0;
    struct sockaddr_in serv_addr;

    sock = socket(AF_INET, SOCK_STREAM, 0);
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons(PORT);
    inet_pton(AF_INET, "127.0.0.1", &serv_addr.sin_addr);
    connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr));
    start_renderer();
    std::cout << "Select User Role:\n1. Disabled (Translates incoming to ISL)\n2. Normal User\nEnter 1 or 2: ";
    std::cin >> user_type;
    std::cin.ignore(); // Clear the newline

    // Start a background thread to listen for incoming messages
    std::thread listener(receive_messages, sock);
    listener.detach();

    std::string input;
    while (true) {
        std::cout << "You: ";
        std::getline(std::cin, input);
        
        if (input == "exit") break;

        // Send raw English to the server to be routed
        send(sock, input.c_str(), input.length(), 0);
    }

    close(sock);
    return 0;
}