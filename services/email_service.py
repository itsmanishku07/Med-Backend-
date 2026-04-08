import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

def send_verification_email(user_email, user_name, verification_link):
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', 587))
    smtp_email = os.getenv('SMTP_EMAIL')
    smtp_password = os.getenv('SMTP_APP_PASSWORD')

    if not smtp_email or not smtp_password:
        print("Error: SMTP credentials missing in .env")
        return False

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
            body {{ font-family: 'Inter', -apple-system, sans-serif; line-height: 1.6; color: #1a202c; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
            .header {{ text-align: center; margin-bottom: 40px; }}
            .logo {{ width: 48px; hieght: 48px; margin-bottom: 16px; }}
            .card {{ background: #ffffff; border-radius: 24px; padding: 40px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }}
            h1 {{ font-size: 24px; font-weight: 700; color: #111827; margin-bottom: 16px; margin-top: 0; }}
            p {{ margin-bottom: 24px; font-size: 16px; color: #4a5568; }}
            .button {{ display: inline-block; padding: 16px 32px; background: #2563eb; color: #ffffff !important; text-decoration: none; border-radius: 12px; font-weight: 600; text-align: center; transition: background 0.2s; }}
            .footer {{ text-align: center; margin-top: 40px; font-size: 14px; color: #718096; }}
            .divider {{ height: 1px; background: #e2e8f0; margin: 32px 0; }}
        </style>
    </head>
    <body style="background-color: #f8fafc;">
        <div class="container">
            <div class="header">
                <h2 style="color: #2563eb; margin: 0; font-weight: 800;">MedReport AI</h2>
            </div>
            <div class="card">
                <h1>Verify your email address</h1>
                <p>Hello {user_name},</p>
                <p>Welcome to MedReport AI. To complete your registration and activate your account, please confirm your email address by clicking the button below:</p>
                
                <div style="text-align: center; margin: 32px 0;">
                    <a href="{verification_link}" class="button">Verify Email Address</a>
                </div>
                
                <p style="font-size: 14px; color: #718096;">If the button above doesn't work, copy and paste this link into your browser:</p>
                <p style="font-size: 13px; word-break: break-all; color: #2563eb; text-decoration: underline;">{verification_link}</p>
                
                <div class="divider"></div>
                
                <p style="font-size: 14px; margin-bottom: 0;">If you did not request this email, you can safely ignore it.</p>
            </div>
            <div class="footer">
                &copy; 2026 MedReport AI. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """

    message = MIMEMultipart("alternative")
    message["Subject"] = "Verify your MedReport AI account"
    message["From"] = f"MedReport AI <{smtp_email}>"
    message["To"] = user_email

    text_content = f"Hello {user_name},\n\nWelcome to MedReport AI. Please verify your email by clicking the link below:\n{verification_link}"

    message.attach(MIMEText(text_content, "plain"))
    message.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, user_email, message.as_string())
        return True
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False
