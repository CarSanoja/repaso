from repaso.schemas.channel import OutboundMessage
from repaso.schemas.family import Family
from repaso.tools.telegram import ChannelSender


def deliver(messages: list[OutboundMessage], sender: ChannelSender) -> list[str]:
    return [sender.send(message) for message in messages]


def deliver_for_family(
    messages: list[OutboundMessage], family: Family, sender: ChannelSender
) -> list[str]:
    stamped = [
        message.model_copy(update={"channel": family.channel, "chat_ref": family.chat_ref})
        for message in messages
    ]
    return deliver(stamped, sender)
