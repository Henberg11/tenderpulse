import asyncio
from app.services.notifications import send_alert

async def main():
    print("Sending test alert...")
    await send_alert(
        subject="Test alert -- TenderPulse email is working (rebuilt)",
        message="This confirms your new Gmail app password is correctly wired up after the full rebuild.",
    )
    print("Done. Check your inbox.")

if __name__ == "__main__":
    asyncio.run(main())