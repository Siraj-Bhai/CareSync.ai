from twilio.rest import Client
from dotenv import load_dotenv
import os

load_dotenv()

client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

call = client.calls.create(
    twiml="""
        <Response>
            <Say voice="alice" language="en-IN">
                MindGuard Emergency Alert.
                Patient John D. has a crisis risk score of 87 out of 100.
                Triggered signals: Hopelessness and Suicidal Ideation.
                Please check the dashboard immediately and take action.
            </Say>
        </Response>
    """,
    from_="+19786843927",
    to="+919344238852"
)

print("Call SID :", call.sid)
print("Status   :", call.status)   # queued → ringing → in-progress → completed

from twilio.rest import Client
import os
from dotenv import load_dotenv

load_dotenv()

client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

message = client.messages("SM434d60a1567582af1f204d34f7e80b7c").fetch()

print("Status :", message.status)        # should say "delivered"
print("To     :", message.to)
print("Sent at:", message.date_sent)
print("Error  :", message.error_code)    # None if successful