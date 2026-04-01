import os
import json
import logging
from pywebpush import webpush, WebPushException

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY', '')
VAPID_PUBLIC_KEY  = os.getenv('VAPID_PUBLIC_KEY', '')
VAPID_CLAIMS      = {'sub': os.getenv('VAPID_CLAIMS_EMAIL', 'mailto:admin@medreport.ai')}


def send_push(endpoint: str, p256dh: str, auth: str, title: str, body: str, data: dict = None) -> bool:
    payload = json.dumps({'title': title, 'body': body, 'data': data or {}})
    try:
        webpush(
            subscription_info={'endpoint': endpoint, 'keys': {'p256dh': p256dh, 'auth': auth}},
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
        )
        return True
    except WebPushException as e:
        status = e.response.status_code if e.response is not None else 'N/A'
        logger.warning(f'Push failed (status {status}): {e}')
        return False
    except Exception as e:
        logger.error(f'Push error: {e}')
        return False
