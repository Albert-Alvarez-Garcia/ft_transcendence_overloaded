import smtplib
import ssl
from email.message import EmailMessage

from backend import config


def send_verification(to: str, link: str):
    if not config.SMTP_HOST or not config.SMTP_FROM:
        raise RuntimeError("Faltan SMTP_HOST o SMTP_FROM en el entorno del backend")
    msg = EmailMessage()
    msg["Subject"] = "Confirma tu cuenta"
    msg["From"] = config.SMTP_FROM
    msg["To"] = to
    msg.set_content("Hola,\n\nConfirma tu cuenta abriendo este enlace (caduca en 24 horas):\n\n" + link +
                    "\n\nSi no has sido tu, ignora este correo.\n")
    ctx = ssl.create_default_context()
    if config.SMTP_PORT == 465:
        server = smtplib.SMTP_SSL(config.SMTP_HOST, 465, context=ctx, timeout=15)
    else:
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
        server.ehlo()
        if server.has_extn("starttls"):
            server.starttls(context=ctx)
            server.ehlo()
        elif config.SMTP_USER:
            raise RuntimeError("El servidor SMTP no ofrece STARTTLS: no se envian credenciales sin cifrar")
    with server:
        if config.SMTP_USER:
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.send_message(msg)
