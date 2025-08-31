import asyncio
import logging
from typing import List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.database import AsyncSessionLocal
from ...database.repositories.mj_network import MJNetworkRepository
from datetime import datetime, timedelta, timezone  # Add timezone
from ..mj_network.mj_communication import MJCommunicationService

logger = logging.getLogger("session_processor")

class SessionProcessor:
    """Background service for processing active auto-chat sessions"""
    
    def __init__(self):
        self.is_running = False
        self.check_interval = 1  # Check every 30 seconds
    
    async def start(self):
        """Start the background session processor"""
        if self.is_running:
            return
            
        self.is_running = True
        logger.info("🔄 Session processor started")
        
        while self.is_running:
            try:
                await self.process_active_sessions()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"❌ Session processor error: {e}")
                await asyncio.sleep(5)  # Short wait before retrying
    
    async def stop(self):
        """Stop the background session processor"""
        self.is_running = False
        logger.info("🔄 Session processor stopped")
    
    async def process_active_sessions(self):
        """Process all active sessions that need responses"""
        
        async with AsyncSessionLocal() as db:
            try:
                network_repo = MJNetworkRepository(db)
                communication_service = MJCommunicationService(db)
                
                # Get sessions ready for turn processing
                ready_sessions = await network_repo.conversations.get_sessions_ready_for_turn()
                
                if not ready_sessions:
                    return  # No sessions to process
                
                logger.info(f"🔄 Processing {len(ready_sessions)} active sessions")
                
                for session in ready_sessions:
                    try:
                        await self._process_session_turn(session, communication_service)
                    except Exception as e:
                        logger.error(f"❌ Failed to process session {session.id}: {e}")
                
            except Exception as e:
                logger.error(f"❌ Error in process_active_sessions: {e}")
    
    async def _process_session_turn(self, session, communication_service):
        """Process a single session turn"""
        
        logger.info(f"🎯 Processing turn for session {session.id} (turn {session.turn_count}/{session.max_turns})")
        
        # Check if session has expired
        if session.session_expires_at and session.session_expires_at < datetime.now(timezone.utc):

            await communication_service.network_repo.conversations.end_session(session.id, "expired")
            logger.info(f"⏰ Session {session.id} expired")
            return
        
        # Check if max turns reached
        if session.turn_count >= session.max_turns:
            await communication_service.network_repo.conversations.end_session(session.id, "completed")
            logger.info(f"✅ Session {session.id} completed (max turns reached)")
            return
        
        # Generate automatic response
        try:
            result = await communication_service._generate_auto_response(session.id)
            logger.info(f"✅ Generated response for session {session.id}: turn {result['turn_count']}")
            
            # Check if session completed after this response
            if result['session_status'] == 'completed':
                logger.info(f"🎉 Session {session.id} completed after achieving objective")
                
        except Exception as e:
            logger.error(f"❌ Failed to generate response for session {session.id}: {e}")
    
    async def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        
        async with AsyncSessionLocal() as db:
            try:
                network_repo = MJNetworkRepository(db)
                
                # Get all active sessions
                active_sessions = await network_repo.conversations.get_active_sessions()
                
                expired_count = 0
                for session in active_sessions:
                    if session.session_expires_at and session.session_expires_at < datetime.now(timezone.utc):

                        await network_repo.conversations.end_session(session.id, "expired")
                        expired_count += 1
                
                if expired_count > 0:
                    logger.info(f"🧹 Cleaned up {expired_count} expired sessions")
                    
            except Exception as e:
                logger.error(f"❌ Error in cleanup_expired_sessions: {e}")

# Global session processor instance
session_processor = SessionProcessor()