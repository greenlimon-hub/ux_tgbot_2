from aiogram.filters.callback_data import CallbackData


class SupportReplyCallback(CallbackData, prefix="support_reply"):
    request_id: int