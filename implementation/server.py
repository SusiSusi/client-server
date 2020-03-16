import asyncio
import random

## Suvi Sipilä, 014220326

class ServerProtocol:
    def __init__(self):
        self.numberOfPackets = 0
        self.received_message = ""
        self.packetA = []
        self.packetB = []
        self.packetC = []
        self.clients = []

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        variant = int.from_bytes(data[0: 2], 'big')
        message = data[2:]
        if variant == 0: ## Game over
            self.game_over(addr)
        elif variant == 1: ## First Hello-message
            self.send_settings(addr)
            self.clients.append(addr)
            print("***************************")
        elif variant == 2: ## Client closes the connection
            for index, client in enumerate(self.clients, start=0):
                if client == addr:
                    del self.clients[index]
                    print("***************************")
                    print("Server removed client: ", client)
        elif variant == 4: ## Receive packet A
            self.packetA = message
        elif variant == 5: ## Receive packet B
            self.packetB = message
        elif variant == 6: ## Receive packet C
            self.packetC = message 
        elif variant == 7: ## One packet group
            self.decode_XOR(addr)
        elif variant == 8: ## Entire message
            address = self.get_address_toString(addr)
            print("***************************")
            print("Move from the client: ", address)
            print(self.received_message)
            print("***************************")
            self.received_message = ""
            self.forward_all_sent(message, addr)
        else:
            print("Wrong variant")

    def game_over(self, addr):
        address = self.get_address_toString(addr)
        message = "Game over! Winner is: " + address
        print("***************************")
        print(message)
        print("***************************")
        for index, client in enumerate(self.clients, start=0):
            try:  
                packet = self.add_variant(message.encode(), 0)
                self.transport.sendto(packet, client)
            except ConnectionResetError:
                print("Client %r has closed the connection" % client)
                del self.clients[index]
        self.clients = []

    def send_settings(self, addr):
        packets = self.create_UDP_packets()
        print("Sending game instuctions to", addr)
        print("***************************")
        for i in range(0, len(packets), 2):
            if not self.numberOfPackets % 2 == 0 and i == len(packets) - 1:
                ## Last packet when numberOfPackets is odd, so packetA is "empty"
                indexB = len(packets) - 1
                packetA = bytearray(len(packets[indexB]))
                packetB = bytearray(packets[indexB])
            else:
                indexA = i
                indexB = i + 1
                packetA = bytearray(packets[indexA])
                packetB = bytearray(packets[indexB])
            packetC = bytearray(len(packetB))
            for x in range(len(packetB)):
                packetC[x] = packetA[x] ^ packetB[x]
            self.transport.sendto(self.add_variant(packetA, 4), addr)    
            self.transport.sendto(self.add_variant(packetB, 5), addr) 
            self.transport.sendto(self.add_variant(packetC, 6), addr) 
            packet = self.create_sent_message()
            self.transport.sendto(packet, addr) # One group A, B, C is sent
        message = "All sent"
        packet = self.add_variant(message.encode(), 9)
        self.transport.sendto(packet, addr)

    def create_sent_message(self):
        message = "Sent"
        packet = self.add_variant(message.encode(), 7)
        return packet

    def create_UDP_packets(self):
        packets = {}
        message = self.read_from_file()
        self.numberOfPackets = int(len(message) / 100)
        lastPacketSize = len(message) - (self.numberOfPackets * 100)
        if lastPacketSize > 0:
            self.numberOfPackets += 1
        # packets size 100 bytes
        for i in range(0, self.numberOfPackets):
              packets[i] = message[100 * i : 100 * (i + 1)].encode() 
        if self.numberOfPackets % 2 == 0:
            self.numberOfPackets += int(self.numberOfPackets / 2)
        else:
            self.numberOfPackets += int(self.numberOfPackets / 2) + 2
        print("***************************")
        print("Data size: ", len(message))
        print("Number of packets: ", self.numberOfPackets)    
        print("Last packet size: ", lastPacketSize)
        print("***************************")
        return packets

    def read_from_file(self):
        with open('Game_Instructions.txt', 'r') as file:
            data = file.read().replace('\n', '')
        file.closed
        return data

    def decode_XOR(self, addr):
        if self.packetA and self.packetB:
            ## A and B received
            self.received_message += self.packetA.decode() + self.packetB.decode()
        elif self.packetA and self.packetC:
            ## A and C received
            packetB = self.create_lost_packet_with_XOR(self.packetA, self.packetC)
            self.received_message += self.packetA.decode() + packetB.decode()
        elif self.packetB and self.packetC:
            ## B and C received
            packetA = self.create_lost_packet_with_XOR(self.packetB, self.packetC)
            self.received_message += packetA.decode() + self.packetB.decode()
        else:
            print("Lost too many packets")       
        print("***************************")
        self.forward_packets(addr)
        self.packetA = []
        self.packetB = []
        self.packetC = []          

    def create_lost_packet_with_XOR(self, packetA, packetB):
        packetC = bytearray(len(packetB))
        for i in range(len(packetB)):
            packetC[i] = packetA[i] ^ packetB[i]
        return packetC

    def forward_packets(self, addr):
        for index, client in enumerate(self.clients, start=0):
            if client != addr:
                try:  
                    print("Forwarding packets from %r to %s " % (addr, client))
                    if self.packetA:
                        packetA = self.add_variant(self.packetA, 4)
                        self.transport.sendto(packetA, client)
                    if self.packetB:
                        packetB = self.add_variant(self.packetB, 5)
                        self.transport.sendto(packetB, client)
                    if self.packetC:
                        packetC = self.add_variant(self.packetC, 6)
                        self.transport.sendto(packetC, client)
                    packet = self.create_sent_message() 
                    self.transport.sendto(packet, client) # One group A, B, C is sent
                except ConnectionResetError:
                    print("Client %r has closed the connection" % client)
                    del self.clients[index]

    def forward_all_sent(self, message, addr):
        for index, client in enumerate(self.clients, start=0):
            if client != addr:
                try:  
                    packet = self.add_variant(message, 8)
                    self.transport.sendto(packet, client)
                except ConnectionResetError:
                    print("Client %r has closed the connection" % client)
                    del self.clients[index]

    def add_variant(self, packet, variant):
        variantToBytes = variant.to_bytes(2, 'big')
        return variantToBytes + packet

    def get_address_toString(self, addr):
        toString = [str(i) for i in addr]
        address = ' '.join(toString)
        return address

async def main():
    print("Starting server")
    loop = asyncio.get_running_loop()

    # One protocol instance will be created to serve all
    # client requests.
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ServerProtocol(),
        local_addr=('127.0.0.1', 9999))

    try:
        await asyncio.sleep(3600)  # Serve for 1 hour
    finally:
        transport.close()


asyncio.run(main())
