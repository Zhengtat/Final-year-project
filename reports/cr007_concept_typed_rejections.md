# Domain/range rejections with a generic `Concept` endpoint (slice3_a1, $0 listing)

- 2-perspective-race-to-the-edge: **bit pipe** (Concept) —[causes]→ **scalable cloud service** (Concept)  
  "bit-pipe, allowing cloud providers to excel at what they do best: run scalable cloud services"  
  check: c_scalable_cloud_service has type 'Concept', not in range_types ['Event', 'State', 'Property'] of 'causes'
- 1.3: **application** (Concept) —[acts_on]→ **message** (DataUnit)  
  "an application can send and receive messages"  
  check: c_application has type 'Concept', not in domain_types ['Component', 'Protocol', 'Mechanism', 'Layer'] of 'acts_on'
- 3.3: **network** (Concept) —[has_property]→ **prefix** (Concept)  
  "share a common prefix, which means that each block must contain a number of class C networks"  
  check: c_prefix has type 'Concept', not in range_types ['Property', 'Parameter'] of 'has_property'
- 3.2: **port** (Parameter) —[acts_on]→ **frame** (Concept)  
  "a frame from host A that is addressed to host B arrives on port 1"  
  check: c_port has type 'Parameter', not in domain_types ['Component', 'Protocol', 'Mechanism', 'Layer'] of 'acts_on'
- 2-perspective-race-to-the-edge: **network operator** (Concept) —[uses]→ **cloud technology** (Concept)  
  "network operators believe that by building the next generation access network using cloud technology"  
  check: c_network_operator has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component'] of 'uses'
- 3.4: **node** (Concept) —[acts_on]→ **link-state information** (DataUnit)  
  "all the nodes participating in the routing protocol get a copy of the link-state information from all the other nodes"  
  check: c_node has type 'Concept', not in domain_types ['Component', 'Protocol', 'Mechanism', 'Layer'] of 'acts_on'
- 1.2: **packet-switched network** (Concept) —[uses]→ **store-and-forward** (Mechanism)  
  "Packet-switched networks typically use a strategy called store-and-forward"  
  check: c_packet_switched_network has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component'] of 'uses'
- 2.7: **chipping code** (DataUnit) —[acts_on]→ **signal** (Concept)  
  "an n-bit chipping code, spread the signal"  
  check: c_chipping_code has type 'DataUnit', not in domain_types ['Component', 'Protocol', 'Mechanism', 'Layer'] of 'acts_on'
- 2.5: **LFS** (State) —[identifies]→ **frame** (Concept)  
  "LFS denotes the sequence number of the last frame sent."  
  check: c_lfs has type 'State', not in domain_types ['Identifier', 'Parameter', 'Property'] of 'identifies'
- 3.1: **switch** (Component) —[causes]→ **path** (Concept)  
  "paths (perhaps because of a change in the forwarding table at some switch in the network)"  
  check: c_path has type 'Concept', not in range_types ['Event', 'State', 'Property'] of 'causes'
- 2.7: **node** (Concept) —[performs]→ **active scanning** (Mechanism)  
  "active scanning since the node is actively searching for an access point"  
  check: c_node has type 'Concept', not in domain_types ['Protocol', 'Component', 'Mechanism'] of 'performs'
- 3.4: **node** (Concept) —[acts_on]→ **routing update** (DataUnit)  
  "a given node decides to send a routing update to its neighbors"  
  check: c_node has type 'Concept', not in domain_types ['Component', 'Protocol', 'Mechanism', 'Layer'] of 'acts_on'
- 3.4: **Checksum** (Concept) —[acts_on]→ **authentication** (Mechanism)  
  "except the authentication data, is protected by a 16-bit checksum"  
  check: c_checksum has type 'Concept', not in domain_types ['Component', 'Protocol', 'Mechanism', 'Layer'] of 'acts_on'
- 3.4: **Checksum** (Concept) —[has_purpose]→ **cryptographic authentication** (Mechanism)  
  "a cryptographic authentication checksum is used"  
  check: c_checksum has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component', 'DataUnit', 'Parameter'] of 'has_purpose'
- 1.4: **Internet** (Concept) —[uses]→ **general-purpose computer** (Component)  
  "the Internet such a runaway success is the fact that so much of its functionality is provided by software running on general-purpose computers"  
  check: c_internet has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component'] of 'uses'
- 3.3: **addressing scheme** (Mechanism) —[has_property]→ **global uniqueness** (Concept)  
  "Global uniqueness is the first property that should be provided in an addressing scheme"  
  check: c_global_uniqueness has type 'Concept', not in range_types ['Property', 'Parameter'] of 'has_property'
- 2.5: **implementation** (Concept) —[performs]→ **Piggybacking** (Mechanism)  
  "implementation does not support piggybacking ACKs on data frames"  
  check: c_implementation has type 'Concept', not in domain_types ['Protocol', 'Component', 'Mechanism'] of 'performs'
- 1-perspective-feature-velocity: **cloud providers** (Concept) —[uses]→ **agile engineering processes** (Mechanism)  
  "cloud providers, which can be summarized as having two major themes: (1) take advantage of commodity hardware and move all intelligence into software, and (2) adopt agile engineering processes"  
  check: c_cloud_providers has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component'] of 'uses'
- 2.8: **network** (Concept) —[has_property]→ **point-to-multipoint design** (Mechanism)  
  "point-to-multipoint design, which means the network is structured as a tree"  
  check: c_point_to_multipoint_design has type 'Mechanism', not in range_types ['Property', 'Parameter'] of 'has_property'
- 1.1: **page** (DataUnit) —[increases]→ **Internet** (Concept)  
  "over the Internet, and many more than that if the web page is complicated with lots of embedded objects"  
  check: c_internet has type 'Concept', not in range_types ['Parameter', 'Property'] of 'increases'
- 2.5: **High-level protocol** (Concept) —[performs]→ **send operation** (Mechanism)  
  "a high-level protocol invokes the services of a low-level protocol by calling the send operation"  
  check: c_high_level_protocol has type 'Concept', not in domain_types ['Protocol', 'Component', 'Mechanism'] of 'performs'
- 3.5: **forwarding** (Concept) —[acts_on]→ **packet** (DataUnit)  
  "receive packets on one of its interfaces, perform any of the switching or forwarding functions described in this chapter, and send packets out another of its interfaces"  
  check: c_forwarding has type 'Concept', not in domain_types ['Component', 'Protocol', 'Mechanism', 'Layer'] of 'acts_on'
- 1.4: **UDP** (Concept) —[has_purpose]→ **message-oriented service** (Concept)  
  "message-oriented service, such as that provided by UDP"  
  check: c_udp has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component', 'DataUnit', 'Parameter'] of 'has_purpose'
- 1.5: **network** (Concept) —[acts_on]→ **bit** (Concept)  
  "bits that can be transmitted over the network"  
  check: c_network has type 'Concept', not in domain_types ['Component', 'Protocol', 'Mechanism', 'Layer'] of 'acts_on'
- 1.5: **bit** (Concept) —[has_property]→ **in flight** (State)  
  "bits in the pipe are said to be “in flight,”"  
  check: c_in_flight has type 'State', not in range_types ['Property', 'Parameter'] of 'has_property'
- 2.3: **frame** (Concept) —[uses]→ **sentinel character** (Mechanism)  
  "use special characters known as sentinel characters to indicate where frames start and end"  
  check: c_frame has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component'] of 'uses'
- 1.2: **network** (Concept) —[acts_on]→ **message** (DataUnit)  
  "network:

-  An application programmer would list the services that his or her application needs: for example, a guarantee that each message the application sends will be delivered without error"  
  check: c_network has type 'Concept', not in domain_types ['Component', 'Protocol', 'Mechanism', 'Layer'] of 'acts_on'
- 3.4: **RIP** (Concept) —[identifies]→ **Routing Information Protocol** (Protocol)  
  "Routing Information Protocol (RIP)"  
  check: c_rip has type 'Concept', not in domain_types ['Identifier', 'Parameter', 'Property'] of 'identifies'
- 2.8: **cellular network** (Concept) —[uses]→ **radio spectrum** (Parameter)  
  "cellular networks transmit data at certain bandwidths in the radio spectrum"  
  check: c_cellular_network has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component'] of 'uses'
- 3.1: **datagram network** (Concept) —[uses]→ **source routing** (Mechanism)  
  "Source routing can be used in both datagram networks"  
  check: c_datagram_network has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component'] of 'uses'
- 3.3: **network** (Concept) —[uses]→ **IP** (Concept)  
  "IP is that it runs on all the nodes (both hosts and routers) in a collection of networks and defines the infrastructure that allows these nodes and networks to function as a single logical internetwork"  
  check: c_network has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component'] of 'uses'
- 3-perspective-virtual-networks-all-the-way-down: **application** (Concept) —[uses]→ **physical memory** (Component)  
  "physical memory may be shared by many applications"  
  check: c_application has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component'] of 'uses'
- 2.7: **Wi-Fi** (Concept) —[identifies]→ **802.11 Wi-Fi standards** (Protocol)  
  "IEEE 802.11 standards, often referred to as Wi-Fi"  
  check: c_wi_fi has type 'Concept', not in domain_types ['Identifier', 'Parameter', 'Property'] of 'identifies'
- 2-perspective-race-to-the-edge: **enterprises** (Concept) —[uses]→ **private 5G network** (Protocol)  
  "Enterprises in the automotive, factory, and warehouse space increasingly want to deploy private 5G networks for a variety of physical automation use cases"  
  check: c_enterprises has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component'] of 'uses'
- 2.4: **bit** (Concept) —[has_purpose]→ **error detection** (Mechanism)  
  "error detection capability while sending only k redundant bits"  
  check: c_bit has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component', 'DataUnit', 'Parameter'] of 'has_purpose'
- 3-perspective-virtual-networks-all-the-way-down: **VLAN** (Concept) —[has_purpose]→ **L2 network** (Layer)  
  "VLANs, as described in Section 3.2, are how we typically virtualize an L2 network"  
  check: c_vlan has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component', 'DataUnit', 'Parameter'] of 'has_purpose'
- 3.3: **class D address** (Concept) —[identifies]→ **Multicast group** (Concept)  
  "class D addresses that specify a multicast group"  
  check: c_class_d_address has type 'Concept', not in domain_types ['Identifier', 'Parameter', 'Property'] of 'identifies'
- 1.4: **server** (Concept) —[performs]→ **bind operation** (Mechanism)  
  "The server does this by invoking the following three operations:

The bind operation"  
  check: c_server has type 'Concept', not in domain_types ['Protocol', 'Component', 'Mechanism'] of 'performs'
- 2.1: **electromagnetic wave** (DataUnit) —[has_property]→ **frequency** (Concept)  
  "the frequency, measured in hertz, with which the electromagnetic waves oscillate"  
  check: c_frequency has type 'Concept', not in range_types ['Property', 'Parameter'] of 'has_property'
- 2.7: **node** (Concept) —[acts_on]→ **RTS frame** (DataUnit)  
  "two nodes might detect an idle link and try to transmit an RTS frame"  
  check: c_node has type 'Concept', not in domain_types ['Component', 'Protocol', 'Mechanism', 'Layer'] of 'acts_on'
- 1.1: **interactive application** (Concept) —[acts_on]→ **video** (DataUnit)  
  "interactive applications usually entail audio and/or video flows in both directions"  
  check: c_interactive_application has type 'Concept', not in domain_types ['Component', 'Protocol', 'Mechanism', 'Layer'] of 'acts_on'
- 1-perspective-feature-velocity: **software ecosystem** (Concept) —[uses]→ **Socket API** (Concept)  
  "software ecosystem, it has historically been limited to the applications running on top of the network (e.g., using the Socket API"  
  check: c_software_ecosystem has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component'] of 'uses'
- 3-perspective-virtual-networks-all-the-way-down: **virtual memory** (Mechanism) —[causes]→ **Abstraction** (Concept)  
  "Virtual memory creates an abstraction"  
  check: c_abstraction has type 'Concept', not in range_types ['Event', 'State', 'Property'] of 'causes'
- 3.3: **Broadcast** (Concept) —[triggers]→ **ARP cache** (Component)  
  "when a host broadcasts a query message, each host on the network can learn the sender’s link-level and IP addresses and place that information in its ARP table"  
  check: c_broadcast has type 'Concept', not in domain_types ['Event', 'State'] of 'triggers'
- 1-problem-building-a-network: **network architecture** (Concept) —[has_purpose]→ **network system** (Concept)  
  "a network architecture that identifies the available hardware and software components and shows how they can be arranged to form a complete network system"  
  check: c_network_architecture has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component', 'DataUnit', 'Parameter'] of 'has_purpose'
- 3-perspective-virtual-networks-all-the-way-down: **UDP packet** (DataUnit) —[encapsulates]→ **Ethernet frame** (Concept)  
  "a virtual ethernet frame inside a UDP packet"  
  check: c_ethernet_frame has type 'Concept', not in range_types ['DataUnit'] of 'encapsulates'
- 2.8: **OLT** (Concept) —[acts_on]→ **grant** (DataUnit)  
  "the OLT transmits grants"  
  check: c_olt has type 'Concept', not in domain_types ['Component', 'Protocol', 'Mechanism', 'Layer'] of 'acts_on'
- 1.3: **application** (Concept) —[uses]→ **protocol** (Protocol)  
  "a request/reply protocol would support operations by which an application can send and receive messages"  
  check: c_application has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component'] of 'uses'
- 2-perspective-race-to-the-edge: **CORD** (Concept) —[has_purpose]→ **Cable Head End** (Component)  
  "CORD, which is an acronym for C\ entral O\ ffice R\ e-architected as a D\ atacenter, and as the name suggests, the idea is to build the Telco Central Office (or the Cable Head End, resulting in the acronym HERD)"  
  check: c_cord has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component', 'DataUnit', 'Parameter'] of 'has_purpose'
- 3.5: **software** (Concept) —[has_purpose]→ **forwarding** (Concept)  
  "running suitable software, can receive packets on one of its interfaces, perform any of the switching or forwarding functions"  
  check: c_software has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component', 'DataUnit', 'Parameter'] of 'has_purpose'
- 1.1: **application** (Concept) —[has_purpose]→ **streaming audio and video** (Concept)  
  "application class of the Internet is the delivery of “streaming” audio and video"  
  check: c_application has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component', 'DataUnit', 'Parameter'] of 'has_purpose'
- 1.1: **HTTP** (Concept) —[identifies]→ **Hypertext Transfer Protocol (HTTP)** (Protocol)  
  "the string http indicates that the Hypertext Transfer Protocol (HTTP) should be used to download the page"  
  check: c_http has type 'Concept', not in domain_types ['Identifier', 'Parameter', 'Property'] of 'identifies'
- 1.4: **operations** (Concept) —[has_purpose]→ **protocol suite** (Protocol)  
  "this operation takes three arguments is that the socket interface was designed to be general enough to support any underlying protocol suite"  
  check: c_operations has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component', 'DataUnit', 'Parameter'] of 'has_purpose'
- 3.1: **application** (Concept) —[has_purpose]→ **virtual private network** (Concept)  
  "applications of virtual circuits for many years was the construction of virtual private networks (VPNs)"  
  check: c_application has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component', 'DataUnit', 'Parameter'] of 'has_purpose'
- 1.2: **network** (Concept) —[has_purpose]→ **reliable message delivery** (Mechanism)  
  "reliable message delivery is one of the most important functions that a network can provide."  
  check: c_network has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component', 'DataUnit', 'Parameter'] of 'has_purpose'
- 3.3: **network** (Concept) —[has_purpose]→ **packet** (DataUnit)  
  "networks interconnected to provide some sort of host-to-host packet delivery service"  
  check: c_network has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component', 'DataUnit', 'Parameter'] of 'has_purpose'
- 1-problem-building-a-network: **computer network** (Concept) —[has_purpose]→ **application** (Concept)  
  "computer network, one that has the potential to grow to global proportions and to support applications"  
  check: c_computer_network has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component', 'DataUnit', 'Parameter'] of 'has_purpose'
- 1.2: **node** (Concept) —[acts_on]→ **message** (DataUnit)  
  "A node that is connected to two or more networks is commonly called a router or gateway, and it plays much the same role as a switch—it forwards messages from one network to another."  
  check: c_node has type 'Concept', not in domain_types ['Component', 'Protocol', 'Mechanism', 'Layer'] of 'acts_on'
- 1.3: **Session layer** (Layer) —[has_purpose]→ **application** (Concept)  
  "the session layer provides a name space that is used to tie together the potentially different transport streams that are part of a single application"  
  check: c_session_layer has type 'Layer', not in domain_types ['Protocol', 'Mechanism', 'Component', 'DataUnit', 'Parameter'] of 'has_purpose'
- 2.5: **LFR** (State) —[identifies]→ **frame** (Concept)  
  "LFR denotes the sequence number of the last frame received"  
  check: c_lfr has type 'State', not in domain_types ['Identifier', 'Parameter', 'Property'] of 'identifies'
- 2.7: **radio wave** (Concept) —[causes]→ **point-to-multipoint communication** (Concept)  
  "it naturally supports point-to-multipoint communication, because radio waves sent by one device can be simultaneously received by many devices."  
  check: c_point_to_multipoint_communication has type 'Concept', not in range_types ['Event', 'State', 'Property'] of 'causes'
- 2.3: **SYN character** (DataUnit) —[triggers]→ **frame** (Concept)  
  "sees the next SYN character to start collecting the bytes that make up the next frame"  
  check: c_syn_character has type 'DataUnit', not in domain_types ['Event', 'State'] of 'triggers'
- 2.3: **bit** (Concept) —[has_purpose]→ **clock recovery** (Mechanism)  
  "bit pattern, which is 127 bits long, has plenty of transitions from 1 to 0, so that XORing it with the transmitted data is likely to yield a signal with enough transitions to enable clock recovery"  
  check: c_bit has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component', 'DataUnit', 'Parameter'] of 'has_purpose'
- 2.8: **fiber-to-the-home** (Concept) —[identifies]→ **Passive Optical Network (PON)** (Protocol)  
  "Passive Optical Networks (PON), commonly referred to as fiber-to-the-home"  
  check: c_fiber_to_the_home has type 'Concept', not in domain_types ['Identifier', 'Parameter', 'Property'] of 'identifies'
- 3.3: **address** (Concept) —[identifies]→ **host** (Component)  
  "no two hosts have the same address"  
  check: c_address has type 'Concept', not in domain_types ['Identifier', 'Parameter', 'Property'] of 'identifies'
- 3.1: **cell** (Concept) —[causes]→ **cell tax** (Concept)  
  "The combination of relatively high header-to-payload ratio plus the frequency of sending partially filled cells did actually lead to some noticeable inefficiency in ATM networks that some detractors called the cell tax."  
  check: c_cell_tax has type 'Concept', not in range_types ['Event', 'State', 'Property'] of 'causes'
- 2.6: **network** (Concept) —[uses]→ **shared medium** (Component)  
  "Like the Aloha network, the fundamental problem faced by the Ethernet is how to mediate access to a shared medium"  
  check: c_network has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component'] of 'uses'
- 1.2: **application** (Concept) —[causes]→ **network** (Concept)  
  "networks are constantly changing as technology evolves and new applications are invented"  
  check: c_network has type 'Concept', not in range_types ['Event', 'State', 'Property'] of 'causes'
- 3.4: **load balancing** (Mechanism) —[increases]→ **network** (Concept)  
  "Load balancing—OSPF allows multiple routes to the same place to be assigned the same cost and will cause traffic to be distributed evenly over those routes, thus making better use of the available network capacity."  
  check: c_network has type 'Concept', not in range_types ['Parameter', 'Property'] of 'increases'
- 1.2: **address** (Concept) —[identifies]→ **node** (Concept)  
  "assigning an address to each node"  
  check: c_address has type 'Concept', not in domain_types ['Identifier', 'Parameter', 'Property'] of 'identifies'
- 2.6: **physical medium** (Component) —[causes]→ **collision domain** (Concept)  
  "competing for access to the same link, and, as a consequence, they are said to be in the same collision domain"  
  check: c_collision_domain has type 'Concept', not in range_types ['Event', 'State', 'Property'] of 'causes'
- 2.6: **node** (Concept) —[performs]→ **collision detect** (Mechanism)  
  "“collision detect” means that a node listens as it transmits and can therefore detect"  
  check: c_node has type 'Concept', not in domain_types ['Protocol', 'Component', 'Mechanism'] of 'performs'
- 3.4: **node** (Concept) —[performs]→ **triggered update** (Mechanism)  
  "a triggered update, happens whenever a node notices a link failure or receives an update from one of its neighbors"  
  check: c_node has type 'Concept', not in domain_types ['Protocol', 'Component', 'Mechanism'] of 'performs'
- 3.3: **best-effort service** (Concept) —[uses]→ **reliable service** (Concept)  
  "provide best-effort service over a network that provides a reliable service"  
  check: c_best_effort_service has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component'] of 'uses'
- 3.4: **TOS field** (Parameter) —[has_property]→ **TOS** (Concept)  
  "The TOS information is present to allow OSPF to choose different routes for IP packets based on the value in their TOS field."  
  check: c_tos has type 'Concept', not in range_types ['Property', 'Parameter'] of 'has_property'
- 2.6: **node** (Concept) —[acts_on]→ **frame** (Concept)  
  "nodes sends and receives frames"  
  check: c_node has type 'Concept', not in domain_types ['Component', 'Protocol', 'Mechanism', 'Layer'] of 'acts_on'
- 1-perspective-feature-velocity: **SDN** (Concept) —[identifies]→ **Software Defined Networks** (Concept)  
  "Software Defined Networks (SDN)"  
  check: c_sdn has type 'Concept', not in domain_types ['Identifier', 'Parameter', 'Property'] of 'identifies'
- 1.2: **network** (Concept) —[uses]→ **physical medium** (Component)  
  "a network can consist of two or more computers directly connected by some physical medium"  
  check: c_network has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component'] of 'uses'
- 2.8: **broadband service** (Concept) —[has_purpose]→ **Internet** (Concept)  
  "connect to the Internet over an access or broadband service"  
  check: c_broadband_service has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component', 'DataUnit', 'Parameter'] of 'has_purpose'
- 1.4: **server** (Concept) —[uses]→ **port** (Parameter)  
  "web servers commonly accept connections on port 80"  
  check: c_server has type 'Concept', not in domain_types ['Protocol', 'Mechanism', 'Component'] of 'uses'