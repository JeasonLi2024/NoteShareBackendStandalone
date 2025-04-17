from chat.models import Conversation

def get_conversation_unread_count(conversation, current_user):
    """
    返回单个对话中 current_user 的未读消息数（排除自己发送的消息）。
    """
    return conversation.messages.filter(is_read=False).exclude(sender=current_user).count()

def get_overall_unread_count(user):
    """
    计算当前用户在所有对话中的未读消息总数，
    排除那些免打扰（DND）状态的对话。
    假设对话是双人聊天，且参与者顺序决定作者和访客：
      - 如果当前用户是作者且对话启用了 author_dnd，则跳过
      - 如果当前用户是访客且对话启用了 visitor_dnd，则跳过
    """
    overall = 0
    conversations = Conversation.objects.filter(participants=user)
    for conv in conversations:
        participants = list(conv.participants.all())
        if len(participants) != 2:
            continue  # 非单聊情况下，可以根据需要处理
        if user == conv.author and conv.author_dnd:
            continue
        if user == conv.visitor and conv.visitor_dnd:
            continue
        overall += conv.messages.filter(is_read=False).exclude(sender=user).count()
    return overall
