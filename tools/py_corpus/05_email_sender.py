import smtplib
from email.mime.text import MIMEText

def send_email(host, sender, recipient, subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    server = smtplib.SMTP(host)
    server.sendmail(sender, [recipient], msg.as_string())
    server.quit()
