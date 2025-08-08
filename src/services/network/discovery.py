# src/services/network/discovery.py
import asyncio
import socket
import json
import bluetooth
from typing import Dict, List, Optional, Any
import hashlib
from ...config.settings import Settings
from ...services.memory.redis_client import RedisClient

settings = Settings()

class MJDiscoveryService:
    def __init__(self):
        self.redis = RedisClient()
        self.local_mj_id: Optional[str] = None
        self.discovery_active = False
        self._discovery_task: Optional[asyncio.Task] = None
    
    async def initialize(self, user_id: int, user_name: str):
        """Initialize MJ discovery service"""
        self.local_mj_id = self._generate_mj_id(user_id, user_name)
        await self.redis.connect()
        
        # Register this MJ instance
        await self.redis.register_mj_instance(
            mj_id=self.local_mj_id,
            user_info={
                "user_id": user_id,
                "user_name": user_name,
                "discovery_port": settings.P2P_DISCOVERY_PORT,
                "capabilities": ["chat", "basic_info"],
                "protocol_version": "1.0"
            }
        )
    
    async def start_discovery(self):
        """Start MJ discovery service"""
        if not self.discovery_active:
            self.discovery_active = True
            self._discovery_task = asyncio.create_task(self._discovery_loop())
    
    async def stop_discovery(self):
        """Stop MJ discovery service"""
        self.discovery_active = False
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
    
    async def discover_nearby_mjs(
        self,
        method: str = "wifi",
        radius_km: float = 1.0
    ) -> List[Dict[str, Any]]:
        """Discover nearby MJ instances"""
        
        if method == "wifi":
            return await self._discover_via_wifi()
        elif method == "bluetooth":
            return await self._discover_via_bluetooth()
        else:
            return await self._discover_via_network_scan()
    
    async def _discovery_loop(self):
        """Main discovery loop"""
        while self.discovery_active:
            try:
                # Broadcast our presence
                await self._broadcast_presence()
                
                # Listen for other MJ broadcasts
                await self._listen_for_broadcasts()
                
                # Small delay
                await asyncio.sleep(30)  # Discover every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Discovery loop error: {e}")
                await asyncio.sleep(5)
    
    async def _discover_via_wifi(self) -> List[Dict[str, Any]]:
        """Discover MJs via WiFi network scanning"""
        discovered_mjs = []
        
        try:
            # Get local network range
            local_ip = socket.gethostbyname(socket.gethostname())
            network_base = ".".join(local_ip.split(".")[:-1])
            
            # Scan local network (this is simplified - in production use proper network discovery)
            tasks = []
            for i in range(1, 255):
                ip = f"{network_base}.{i}"
                tasks.append(self._check_mj_at_ip(ip))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, dict):
                    discovered_mjs.append(result)
        
        except Exception as e:
            print(f"WiFi discovery error: {e}")
        
        return discovered_mjs
    
    async def _discover_via_bluetooth(self) -> List[Dict[str, Any]]:
        """Discover MJs via Bluetooth"""
        discovered_mjs = []
        
        try:
            # Scan for Bluetooth devices with MJ service UUID
            # This is a simplified version - actual Bluetooth discovery is more complex
            nearby_devices = bluetooth.discover_devices(lookup_names=True)
            
            for addr, name in nearby_devices:
                if "MJ-" in name:  # Our naming convention
                    discovered_mjs.append({
                        "mj_id": name,
                        "bluetooth_addr": addr,
                        "discovery_method": "bluetooth",
                        "signal_strength": "unknown"  # Would measure actual signal strength
                    })
        
        except Exception as e:
            print(f"Bluetooth discovery error: {e}")
        
        return discovered_mjs
    
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
                "protocol_version": "1.0"
            }
            
            writer.write(json.dumps(discovery_msg).encode())
            await writer.drain()
            
            # Read response
            data = await asyncio.wait_for(reader.read(1024), timeout=2)
            response = json.loads(data.decode())
            
            writer.close()
            await writer.wait_closed()
            
            if response.get("type") == "mj_discovery_response":
                return {
                    "mj_id": response.get("mj_id"),
                    "ip_address": ip,
                    "user_name": response.get("user_name"),
                    "discovery_method": "wifi",
                    "capabilities": response.get("capabilities", [])
                }
        
        except Exception:
            pass  # No MJ instance at this IP
        
        return None
    
    def _generate_mj_id(self, user_id: int, user_name: str) -> str:
        """Generate unique MJ instance ID"""
        data = f"{user_id}:{user_name}:{socket.gethostname()}"
        return f"MJ-{hashlib.md5(data.encode()).hexdigest()[:8]}"
    
    async def _broadcast_presence(self):
        """Broadcast MJ presence to network"""
        # This would implement actual network broadcasting
        pass
    
    async def _listen_for_broadcasts(self):
        """Listen for MJ broadcasts from other instances"""
        # This would implement listening for broadcasts
        pass
