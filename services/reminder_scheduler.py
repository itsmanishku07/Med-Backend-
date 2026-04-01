"""
APScheduler job that runs every minute, checks active medicine reminders,
and sends Web Push notifications to subscribed users.
"""
import logging
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)
_scheduler = None


def _fire_reminders():
    try:
        from config.database import SessionLocal
        from models.db_models import MedicineReminder, PushSubscription
        from services.push_service import send_push

        now = datetime.now()
        hhmm = now.strftime('%H:%M')
        day_name = now.strftime('%a')   # Mon, Tue, …

        with SessionLocal() as session:
            reminders = session.query(MedicineReminder).filter_by(is_active=True).all()
            for r in reminders:
                if r.reminder_time != hhmm:
                    continue
                if r.days and day_name not in r.days:
                    continue

                # Get all push subscriptions for this user
                subs = session.query(PushSubscription).filter_by(user_id=r.user_id).all()
                for sub in subs:
                    body = f'Time to take {r.medicine_name}'
                    if r.dosage:
                        body += f' — {r.dosage}'
                    if r.notes:
                        body += f'. {r.notes}'
                    ok = send_push(
                        endpoint=sub.endpoint,
                        p256dh=sub.p256dh,
                        auth=sub.auth,
                        title='💊 Medicine Reminder',
                        body=body,
                        data={'medicine_name': r.medicine_name, 'dosage': r.dosage or ''},
                    )
                    if not ok:
                        # Subscription expired — remove it
                        session.delete(sub)
            session.commit()
    except Exception as e:
        logger.error(f'Reminder scheduler error: {e}')


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(timezone=pytz.utc)
    _scheduler.add_job(_fire_reminders, 'cron', minute='*', id='medicine_reminders', replace_existing=True)
    _scheduler.start()
    logger.info('Medicine reminder scheduler started')


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
