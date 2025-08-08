# src/services/network/discovery.py - NETWORK-ONLY VERSION
import asyncio
import socket
import json
from typing import Dict, List, Optional, Any
import hashlib
import netifaces
from ...config.settings import Settings
from ...services.memory.redis_client import RedisClient

settings = Settings()

class MJDiscoveryService:
    """Network-only MJ discovery service (no Bluetooth)"""
    
    def __init__(self):
        self.redis = RedisClient()
        self.local_mj_id: Optional[str] = None
        self.discovery_active = False
        self._discovery_task: Optional[asyncio.Task] = None
        self._server_task: Optional[asyncio.Task] = None
    
    async def initialize(self, user_id: int, user_name: str):
        """Initialize MJ discovery service"""
        self.local_mj_id = self._generate_mj_id(user_id, user_name)
        await self.redis.connect()
        
        # Register this MJ instance in Redis
        await self.redis.register_mj_instance(
            mj_id=self.local_mj_id,
            user_info={
                "user_id": user_id,
                "user_name": user_name,
                "discovery_port": settings.P2P_DISCOVERY_PORT,
                "capabilities": ["chat", "basic_info"],
                "protocol_version": "1.0",
                "local_ip": self._get_local_ip()
            }
        )
        
        print(f"🌐 MJ {self.local_mj_id} initialized for network discovery")
    
    async def start_discovery(self):
        """Start network-only MJ discovery service"""
        if not self.discovery_active:
            self.discovery_active = True
            
            # Start discovery server (listens for other MJs)
            self._server_task = asyncio.create_task(self._start_discovery_server())
            
            # Start discovery client (finds other MJs)
            self._discovery_task = asyncio.create_task(self._discovery_loop())
            
            print(f"🔍 Network discovery started on port {settings.P2P_DISCOVERY_PORT}")
    
    async def stop_discovery(self):
        """Stop MJ discovery service"""
        self.discovery_active = False
        
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
        
        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass
        
        print("🛑 Network discovery stopped")
    
    async def discover_nearby_mjs(
        self,
        method: str = "network",  # Only network method now
        radius_km: float = 1.0
    ) -> List[Dict[str, Any]]:
        """Discover nearby MJ instances via network"""
        
        if method == "network":
            return await self._discover_via_network_scan()
        elif method == "redis":
            return await self._discover_via_redis()
        else:
            # Default to network scan
            return await self._discover_via_network_scan()
    
    async def _discovery_loop(self):
        """Main discovery loop - broadcasts presence and scans"""
        while self.discovery_active:
            try:
                # Update our presence in Redis
                await self._update_presence_in_redis()
                
                # Scan for other MJs on network
                nearby_mjs = await self._discover_via_network_scan()
                
                # Log discoveries
                if nearby_mjs:
                    print(f"🔍 Found {len(nearby_mjs)} nearby MJs")
                
                # Wait before next discovery cycle
                await asyncio.sleep(30)  # Discover every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Discovery loop error: {e}")
                await asyncio.sleep(5)
    
    async def _start_discovery_server(self):
        """Start server to respond to discovery requests"""
        try:
            server = await asyncio.start_server(
                self._handle_discovery_request,
                '0.0.0.0',
                settings.P2P_DISCOVERY_PORT
            )
            
            print(f"🖥️ Discovery server listening on port {settings.P2P_DISCOVERY_PORT}")
            
            async with server:
                await server.serve_forever()
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"❌ Discovery server error: {e}")
    
    async def _handle_discovery_request(self, reader, writer):
        """Handle incoming discovery requests from other MJs"""
        try:
            # Read discovery request
            data = await asyncio.wait_for(reader.read(1024), timeout=5)
            
            if not data:
                return
            
            try:
                request = json.loads(data.decode())
            except json.JSONDecodeError:
                return
            
            # Verify it's a valid MJ discovery request
            if request.get("type") != "mj_discovery":
                return
            
            # Prepare response
            response = {
                "type": "mj_discovery_response",
                "mj_id": self.local_mj_id,
                "user_name": "MJ User",  # Would get from user data
                "capabilities": ["chat", "basic_info"],
                "protocol_version": "1.0",
                "discovery_method": "network",
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # Send response
            response_data = json.dumps(response).encode()
            writer.write(response_data)
            await writer.drain()
            
            print(f"📡 Responded to discovery request from {request.get('from_mj_id')}")
            
        except Exception as e:
            print(f"❌ Error handling discovery request: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def _discover_via_network_scan(self) -> List[Dict[str, Any]]:
        """Discover MJs via local network scanning"""
        discovered_mjs = []
        
        try:
            # Get local network info
            local_networks = self._get_local_networks()
            
            # Scan each local network
            for network_info in local_networks:
                network_base = network_info["network_base"]
                
                # Create tasks to scan IPs in parallel (limit to avoid overwhelming)
                scan_tasks = []
                for i in range(1, 255):  # Scan all IPs in subnet
                    ip = f"{network_base}.{i}"
                    if ip != network_info["local_ip"]:  # Don't scan ourselves
                        scan_tasks.append(self._check_mj_at_ip(ip))
                    
                    # Process in batches to avoid too many concurrent connections
                    if len(scan_tasks) >= 20:
                        results = await asyncio.gather(*scan_tasks, return_exceptions=True)
                        for result in results:
                            if isinstance(result, dict):
                                discovered_mjs.append(result)
                        scan_tasks = []
                
                # Process remaining tasks
                if scan_tasks:
                    results = await asyncio.gather(*scan_tasks, return_exceptions=True)
                    for result in results:
                        if isinstance(result, dict):
                            discovered_mjs.append(result)
        
        except Exception as e:
            print(f"❌ Network scan error: {e}")
        
        return discovered_mjs
    
    async def _discover_via_redis(self) -> List[Dict[str, Any]]:
        """Discover MJs via Redis registry (for distributed setup)"""
        try:
            nearby_mjs = await self.redis.discover_nearby_mjs("local_network")
            
            # Filter out ourselves
            filtered_mjs = [
                mj for mj in nearby_mjs 
                if mj.get("mj_id") != self.local_mj_id
            ]
            
            return filtered_mjs
        
        except Exception as e:
            print(f"❌ Redis discovery error: {e}")
            return []
    
    async def _check_mj_at_ip(self, ip: str) -> Optional[Dict[str, Any]]:
        """Check if there's an MJ instance at given IP"""
        try:
            # Try to connect to MJ discovery port
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, settings.P2P_DISCOVERY_PORT),
                timeout=2
            )
            
            # Send discovery handshake
            discovery_msg = {
                "type": "mj_discovery",
                "from_mj_id": self.local_mj_id,
                "protocol_version": "1.0",
                "timestamp": asyncio.get_event_loop().time()
            }
            
            writer.write(json.dumps(discovery_msg).encode())
            await writer.drain()
            
            # Read response
            data = await asyncio.wait_for(reader.read(1024), timeout=2)
            
            writer.close()
            await writer.wait_closed()
            
            if data:
                try:
                    response = json.loads(data.decode())
                    
                    if response.get("type") == "mj_discovery_response":
                        return {
                            "mj_id": response.get("mj_id"),
                            "ip_address": ip,
                            "user_name": response.get("user_name", "Unknown"),
                            "discovery_method": "network",
                            "capabilities": response.get("capabilities", []),
                            "protocol_version": response.get("protocol_version", "1.0"),
                            "signal_strength": "network",  # Network connection is binary
                            "distance_estimate": "local_network"
                        }
                except json.JSONDecodeError:
                    pass
        
        except Exception:
            pass  # No MJ instance at this IP or connection failed
        
        return None
    
    def _get_local_networks(self) -> List[Dict[str, Any]]:
        """Get information about local networks"""
        networks = []
        
        try:
            # Get all network interfaces
            interfaces = netifaces.interfaces()
            
            for interface in interfaces:
                # Get IPv4 addresses for each interface
                addrs = netifaces.ifaddresses(interface)
                
                if netifaces.AF_INET in addrs:
                    for addr_info in addrs[netifaces.AF_INET]:
                        ip = addr_info.get('addr')
                        netmask = addr_info.get('netmask')
                        
                        if ip and netmask and not ip.startswith('127.'):
                            # Calculate network base (assumes /24 subnet)
                            ip_parts = ip.split('.')
                            if len(ip_parts) == 4:
                                network_base = '.'.join(ip_parts[:3])
                                
                                networks.append({
                                    "interface": interface,
                                    "local_ip": ip,
                                    "netmask": netmask,
                                    "network_base": network_base
                                })
        
        except Exception as e:
            print(f"❌ Error getting network interfaces: {e}")
            
            # Fallback: try to get local IP via socket connection
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    local_ip = s.getsockname()[0]
                    ip_parts = local_ip.split('.')
                    if len(ip_parts) == 4:
                        network_base = '.'.join(ip_parts[:3])
                        networks.append({
                            "interface": "default",
                            "local_ip": local_ip,
                            "network_base": network_base
                        })
            except Exception:
                pass
        
        return networks
    
    def _get_local_ip(self) -> str:
        """Get local IP address"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
    
    def _generate_mj_id(self, user_id: int, user_name: str) -> str:
        """Generate unique MJ instance ID"""
        local_ip = self._get_local_ip()
        data = f"{user_id}:{user_name}:{local_ip}:{socket.gethostname()}"
        return f"MJ-{hashlib.md5(data.encode()).hexdigest()[:8]}"
    
    async def _update_presence_in_redis(self):
        """Update our presence in Redis for distributed discovery"""
        try:
            await self.redis.register_mj_instance(
                mj_id=self.local_mj_id,
                user_info={
                    "local_ip": self._get_local_ip(),
                    "discovery_port": settings.P2P_DISCOVERY_PORT,
                    "last_seen": asyncio.get_event_loop().time(),
                    "status": "online"
                },
                ttl=60  # Expire after 1 minute if not updated
            )
        except Exception as e:
            print(f"❌ Error updating Redis presence: {e}")
