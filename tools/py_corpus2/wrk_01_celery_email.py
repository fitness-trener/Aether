from celery import Celery
import smtplib
from email.mime.text import MIMEText

celery_app = Celery("tasks", broker="redis://localhost:6379")

@celery_app.task
def send_welcome_email(address, name):
    msg = MIMEText("Welcome, " + name)
    msg["Subject"] = "Welcome"
    msg["To"] = address
    with smtplib.SMTP("localhost") as server:
        server.send_message(msg)
