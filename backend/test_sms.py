# test_sms.py
import requests
# Patch SSL verification globally — needed behind corporate/college proxies
_orig_request = requests.Session.request
def _patched_request(self, *args, **kwargs):
    kwargs.setdefault("verify", False)
    return _orig_request(self, *args, **kwargs)
requests.Session.request = _patched_request

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import africastalking
from dotenv import load_dotenv
import os

load_dotenv()

africastalking.initialize(
    username=os.getenv("AT_USERNAME"),
    api_key=os.getenv("AT_API_KEY")
)

sms = africastalking.SMS

response = sms.send(
    message="[MindGuard] 🚨 Crisis Alert: John D. — Risk Score: 87/100. Immediate attention required.",
    recipients=["+919344238852"],
    sender_id=os.getenv("AT_SENDER_ID")
)

print(response)
