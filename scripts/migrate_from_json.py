"""
Migration script: JSON -> PostgreSQL.
Migrates existing Opora JSON data to new PostgreSQL database.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from core import configure_logging, get_logger, LogContexts
from db import get_db_session, init_db
from db.repositories import UserRepository, SessionRepository, MessageRepository, DecisionLogRepository

logger = get_logger(LogContexts.SERVICE)


async def migrate_patient_record(
    patient_id: str,
    data: dict[str, Any],
    user_repo: UserRepository,
    session_repo: SessionRepository,
    message_repo: MessageRepository,
    decision_repo: DecisionLogRepository,
) -> None:
    """Migrate single patient record from JSON to DB."""
    logger.info("migrating_patient", patient_id=patient_id)
    
    # Extract patient record info
    patient_record = data.get("patient_record", {})
    sessions = data.get("sessions", {})
    
    # Create user (using patient_id as telegram_id for migration)
    telegram_id = int(patient_id.replace("patient_", "").replace("user_", ""))
    
    existing_user = await user_repo.get_by_telegram_id(telegram_id)
    if existing_user:
        user = existing_user
    else:
        user = await user_repo.create_from_telegram(
            telegram_id=telegram_id,
            username=f"migrated_user_{patient_id}",
        )
        
        # Update medical record
        await user_repo.update_medical_record(
            user_id=user.id,
            pseudonym=patient_record.get("patient pseudonym"),
            age=patient_record.get("patient age"),
            mental_health=patient_record.get("mental health history"),
            physical_health=patient_record.get("physical health history"),
            problems=patient_record.get("current problems and symptoms"),
        )
    
    # Migrate sessions
    for session_key, session_data in sessions.items():
        session_num = int(session_key.replace("session_", ""))
        
        # Create session
        session = await session_repo.create_session(
            user_id=user.id,
            session_number=session_num,
            therapy_type=session_data.get("therapy", "unspecified therapy"),
        )
        
        # Migrate dialogs
        dialogs = session_data.get("dialogs", [])
        for idx, dialog in enumerate(dialogs, start=1):
            # Parse dialog format: "PATIENT: text" or "DOCTOR: text"
            if dialog.startswith("PATIENT:"):
                role = "patient"
                content = dialog[8:].strip()
            elif dialog.startswith("DOCTOR:"):
                role = "doctor"
                content = dialog[7:].strip()
            else:
                # Try to infer
                if idx % 2 == 1:
                    role = "patient"
                else:
                    role = "doctor"
                content = dialog
            
            await message_repo.create_message(
                session_id=session.id,
                role=role,
                content=content,
                message_number=idx,
            )
        
        # End session if it has dialogs
        if dialogs:
            await session_repo.end_session(session.id)
    
    logger.info("patient_migrated", patient_id=patient_id, user_id=user.id)


async def migrate_decision_data(
    patient_id: str,
    data: dict[str, Any],
    decision_repo: DecisionLogRepository,
    user_repo: UserRepository,
) -> None:
    """Migrate decision data from JSON file."""
    logger.info("migrating_decisions", patient_id=patient_id)
    
    telegram_id = int(patient_id.replace("patient_", "").replace("user_", ""))
    user = await user_repo.get_by_telegram_id(telegram_id)
    
    if not user:
        logger.warning("user_not_found_for_decisions", patient_id=patient_id)
        return
    
    # Get user sessions to map decision data
    from db.repositories import SessionRepository
    session_repo = SessionRepository(decision_repo.session)
    sessions = await session_repo.get_all_user_sessions(user.id)
    session_map = {s.session_number: s.id for s in sessions}
    
    # Migrate decision data
    for session_key, responses in data.items():
        session_num = int(session_key.replace("session_", ""))
        session_id = session_map.get(session_num)
        
        if not session_id:
            continue
        
        for response_key, decision_data in responses.items():
            response_num = int(response_key.replace("response_", ""))
            
            await decision_repo.log_decision(
                session_id=session_id,
                response_number=response_num,
                memory_invoke_result=decision_data.get("Memory Invoke"),
                is_rejecting=decision_data.get("Whether to Reject or Deviate", False),
                current_therapy=decision_data.get("Current Therapy", "unspecified therapy"),
                current_stage=decision_data.get("Current Stage"),
                primary_emotion=decision_data.get("Primary Emotion"),
                emotional_intensity=decision_data.get("Emotional Intensity"),
                response_strategy=decision_data.get("Response Strategy"),
                strategy_description=decision_data.get("Strategy Description"),
                patient_attitude=decision_data.get("Attitude"),
                decision_snapshot=decision_data,
            )


async def main():
    """Main migration function."""
    configure_logging(level="INFO")
    
    logger.info("migration_started")
    
    # Initialize database
    await init_db()
    
    # Define paths
    save_data_dir = Path("save_data")
    eval_data_dir = Path("eval_data")
    
    if not save_data_dir.exists():
        logger.error("save_data_directory_not_found", path=str(save_data_dir))
        return
    
    async with get_db_session() as session:
        user_repo = UserRepository(session)
        session_repo = SessionRepository(session)
        message_repo = MessageRepository(session)
        decision_repo = DecisionLogRepository(session)
        
        # Migrate patient records
        migrated_count = 0
        for json_file in save_data_dir.glob("*.json"):
            patient_id = json_file.stem
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                await migrate_patient_record(
                    patient_id=patient_id,
                    data=data,
                    user_repo=user_repo,
                    session_repo=session_repo,
                    message_repo=message_repo,
                    decision_repo=decision_repo,
                )
                migrated_count += 1
                
            except Exception as e:
                logger.error("migration_failed_for_patient", patient_id=patient_id, error=str(e))
        
        # Migrate decision data
        if eval_data_dir.exists():
            for json_file in eval_data_dir.glob("decision basis_*.json"):
                patient_id = json_file.stem.replace("decision basis_", "")
                
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    await migrate_decision_data(
                        patient_id=patient_id,
                        data=data,
                        decision_repo=decision_repo,
                        user_repo=user_repo,
                    )
                    
                except Exception as e:
                    logger.error("decision_migration_failed", patient_id=patient_id, error=str(e))
    
    logger.info("migration_completed", migrated_patients=migrated_count)


if __name__ == "__main__":
    asyncio.run(main())
