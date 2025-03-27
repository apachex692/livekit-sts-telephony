import asyncio
import sys
from getpass import getpass
from os import getenv

from dotenv import load_dotenv
from livekit.api import LiveKitAPI
from livekit.protocol.sip import (
    CreateSIPOutboundTrunkRequest,
    DeleteSIPTrunkRequest,
    ListSIPOutboundTrunkRequest,
    SIPOutboundTrunkInfo,
)


def show_usage():
    print("Usage: python script.py <task>")
    print("Available Tasks:")
    print("    - create_trunk")
    print("    - list_trunks")
    print("    - delete_trunk")


async def create_sip_outbound_trunk(livekit_api: LiveKitAPI):
    print("\nEnter Details:")
    default_name = "Twilio SIP Trunk"
    name = input(f"    Trunk Name ({default_name}): ") or default_name

    default_address = getenv("TWILIO_SIP_TERMINATION_ENDPOINT", "")
    address = (
        input(f"    Trunk Address ({default_address}): ") or default_address
    )

    default_numbers = getenv("TWILIO_OUTBOUND_CALLER_NUMBER", "")
    numbers_str = (
        input(f"    Phone Numbers (comma-separated) ({default_numbers}): ")
        or default_numbers
    )
    numbers = [num.strip() for num in numbers_str.split(",")]

    print("From Twilio:")
    default_auth_username = getenv("TWILIO_SIP_AUTH_USERNAME", "")
    auth_username = (
        input(f"    Authentication Username ({default_auth_username}): ")
        or default_auth_username
    )

    default_auth_password = getenv("TWILIO_SIP_AUTH_PASSWORD", "")
    password_prompt = (
        "    Authentication Password (will default to environment variable TWILIO_SIP_AUTH_PASSWORD): "
        if default_auth_password
        else "    Authentication Password: "
    )
    auth_password = getpass(password_prompt) or default_auth_password

    trunk = SIPOutboundTrunkInfo(
        name=name,
        address=address,
        numbers=numbers,
        auth_username=auth_username,
        auth_password=auth_password,
    )

    request = CreateSIPOutboundTrunkRequest(trunk=trunk)
    trunk = await livekit_api.sip.create_sip_outbound_trunk(request)

    print(f"\nCreated:\n{trunk}")
    await livekit_api.aclose()


async def list_sip_outbound_trunks(livekit_api: LiveKitAPI):
    trunks = await livekit_api.sip.list_sip_outbound_trunk(
        ListSIPOutboundTrunkRequest()
    )
    print(f"\nTrunks:\n{trunks}")
    await livekit_api.aclose()


async def delete_sip_outbound_trunk(livekit_api: LiveKitAPI) -> None:
    trunk_id = input("Enter Trunk ID: ")
    response = await livekit_api.sip.delete_sip_trunk(
        DeleteSIPTrunkRequest(sip_trunk_id=trunk_id)
    )
    print("\nDeleted:\n", response)
    await livekit_api.aclose()


async def main():
    print("LiveKit SIP Outbound Trunk Manager")
    if len(sys.argv) < 2:
        show_usage()
        return

    task = sys.argv[1]

    livekit_api = LiveKitAPI()

    if task == "create_trunk":
        await create_sip_outbound_trunk(livekit_api)
    elif task == "delete_trunk":
        await delete_sip_outbound_trunk(livekit_api)
    elif task == "list_trunks":
        await list_sip_outbound_trunks(livekit_api)
    else:
        show_usage()


if __name__ == "__main__":
    load_dotenv(".env.local")
    asyncio.run(main())
