
# Salome

_Doing the dance of the seven veilids._

Salome is a project that leverages the Veilid network to create a file server and client. It includes:

- A server that handles file requests over the Veilid network.
- A client that can request files from the server.
- The client spins up a local proxy for serving the pages to the user.

This project is very much a work in progress. Feel free to take it for a spin, play around with it. PRs welcome.

## Getting Started

### Prerequisites

- Python 3.12.5
- A local Veilid node

### Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/salome.git
    cd salome
    ```

2. Install the dependencies:
    ```sh
    pip install -r requirements.txt
    ```

### Running the Server

To start the Veilid file server, run:
```sh
python server.py
```

### Running the Client

To request a file from the server, run:
```sh
python client.py <dht_key>
```
Replace `<dht_key>` with the actual DHT key where the server's private route blob is stored.

You can pass --port #### to change the port number. 


