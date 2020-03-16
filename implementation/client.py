import asyncio
import random
import sys
import select

  ## Suvi Sipilä, 014220326

class ClientProtocol:
    def __init__(self, on_con_lost, dataLoss):
        self.message = ""
        self.received_message = ""
        self.received_instuctions = False
        self.received_all_packets = True
        self.numberOfPackets = 0
        self.dataLoss = dataLoss
        self.packetA = []
        self.packetB = []
        self.packetC = []
        self.transport = None
        self.on_con_lost = on_con_lost

    def connection_made(self, transport):
        self.transport = transport
        self.send_hello()

    def close_the_socket(self):
        print("Close the socket")
        self.transport.close()

    def error_received(self, exc):
        print('Error received:', exc)

    def connection_lost(self, exc):
        print("Connection closed")
        self.on_con_lost.set_result(True)

    def datagram_received(self, data, addr):
        variant = int.from_bytes(data[0: 2], 'big')
        message = data[2:]
        if variant == 0: ## Game over
            self.received_instuctions = False
            self.received_all_packets = False
            print("***************************")
            print(message.decode())
            print("***************************")
            self.close_the_socket()
        if variant == 1: ## First Hello-message (not used on client side)
            print("Received:", message.decode())
        elif variant == 4: ## Receive packet A
            self.received_all_packets = False
            self.packetA = message
        elif variant == 5: ## Receive packet B 
            self.received_all_packets = False
            self.packetB = message
        elif variant == 6: ## Receive packet C
            self.received_all_packets = False
            self.packetC = message 
        elif variant == 7: ## One packet group
            self.received_all_packets = False
            self.decode_XOR(addr)
        elif variant == 8: ## Entire message
            self.received_all_packets = True
            print("***************************")
            print("Received:", self.received_message)
            self.received_message = ""
        elif variant == 9: ## Entire game instructions
            self.received_instuctions = True
            self.received_all_packets = True
            print("***************************")
            print("Received:", self.received_message)
            self.received_message = ""
        if self.received_instuctions and self.received_all_packets:
            self.send_message()

    def create_UDP_packets(self):
        packets = {}
        self.numberOfPackets = int(len(self.message) / 2)
        lastPacketSize = len(self.message) - (self.numberOfPackets * 2)
        if lastPacketSize > 0:
            self.numberOfPackets += 1
        # packets size 2 bytes
        for i in range(0, self.numberOfPackets):
              packets[i] = self.message[2 * i : 2 * (i + 1)].encode() 
        if self.numberOfPackets % 2 == 0:
            self.numberOfPackets += int(self.numberOfPackets / 2)
        else:
            self.numberOfPackets += int(self.numberOfPackets / 2) + 2
        print("***************************")
        print("Data size: ", len(self.message))
        print("Number of packets: ", self.numberOfPackets)    
        print("Last packet size: ", lastPacketSize)
        print("***************************")
        return packets

    def add_variant(self, value, variant):
        variantToBytes = variant.to_bytes(2, 'big')
        return variantToBytes + value

    def send_hello(self):
        print("Sending fist Hello-message")
        print("***************************")
        message = "Hello"
        variant = 1
        variantToBytes = variant.to_bytes(2, 'big')
        packet = variantToBytes + message.encode()
        self.transport.sendto(packet)
   
    def send_message(self):
        if self.received_instuctions and self.received_all_packets:
            print("***************************")
            print("Press x to send move: ")
            i, o, e = select.select( [sys.stdin], [], [], 10 ) ## client has 10 seconds to answer
            if (i):
                clientInput = sys.stdin.readline().strip()
                if clientInput == 'x':
                    self.numberOfPackets = 0
                    message = input("Please enter your move: ")
                    self.message = message
                    sendPackets = self.create_UDP_packets() 
                    self.create_XOR(sendPackets)
                elif clientInput == 'win':
                    message = "I win!"
                    packet = self.add_variant(message.encode(), 0)
                    self.transport.sendto(packet)
                elif clientInput == 'out':
                    message = "Im out"
                    packet = self.add_variant(message.encode(), 2)
                    self.transport.sendto(packet)
                    self.close_the_socket()
                else:
                    return
            else:
                print("Client listens...")

    def create_XOR(self, packets):
        print("Creating XOR packets")
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
            self.send_XOR(self.add_variant(packetA, 4), ('A_' + str(indexA)))
            self.send_XOR(self.add_variant(packetB, 5), ('B_' + str(indexB)))
            self.send_XOR(self.add_variant(packetC, 6), ('C_' + str(indexA) + '_' + str(indexB)))
            message = "Sent"
            packet = self.add_variant(message.encode(), 7)
            self.transport.sendto(packet) # One group A, B, C is sent
        message = "All sent"
        packet = self.add_variant(message.encode(), 8)
        self.transport.sendto(packet)
        
    def send_XOR(self, packet, key):
        randomNumber = self.get_random_number()
        if (randomNumber >= self.dataLoss):
            self.transport.sendto(packet)
        else:
            print('Data loss! Packet index %r was not sent.' % key)     

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
        self.packetA = []
        self.packetB = []
        self.packetC = []

    def create_lost_packet_with_XOR(self, packetA, packetB):
        packetC = bytearray(len(packetB))
        for i in range(len(packetB)):
            packetC[i] = packetA[i] ^ packetB[i]
        return packetC
    
    def get_random_number(self):
        randomNumber = random.randint(1, 100) # Generate number between 1 - 100
        return randomNumber


async def main():
    loop = asyncio.get_running_loop()
    on_con_lost = loop.create_future()
    dataLoss = 2 # Data loss rate, percent number (0 - 100 %)
    
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ClientProtocol(on_con_lost, dataLoss),
        remote_addr=('127.0.0.1', 9999))

    try:
        await on_con_lost
    finally:
        transport.close()


asyncio.run(main())