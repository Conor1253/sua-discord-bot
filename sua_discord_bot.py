# ============================================================
#  이수아 디스코드 봇
#  Gemini API + Discord.py
#
#  기능:
#  1. 실시간 대화 (메시지 보내면 이수아가 대답)
#  2. 2시간마다 자동으로 말 걸기
#  3. 대화 기억 (최근 20개 메시지 기억)
#
#  Railway에 올려서 24시간 무료로 실행합니다.
# ============================================================

import discord
import requests
import asyncio
import random
import os
from datetime import datetime


# ─────────────────────────────────────────────
#  [설정] 환경 변수에서 키를 가져옵니다.
#  Railway에서는 Variables 탭에서 설정합니다.
# ─────────────────────────────────────────────

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "여기에_디스코드_봇_토큰")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "여기에_제미나이_API키")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "0"))  # 수아가 말할 채널 ID


# ─────────────────────────────────────────────
#  이수아의 성격 설정 (시스템 프롬프트)
#  이 부분을 수정하면 성격이 바뀝니다.
# ─────────────────────────────────────────────

SUA_PERSONA = """너는 '이수아'라는 20세 여성 캐릭터야.

[성격]
- 비꼬는 말투의 쯘데레. 상대방을 은근히 챙기면서도 절대 솔직하게 표현하지 않아.
- 반말을 쓰고, 귀찮은 척하면서 사실은 신경 쓰고 있어.
- 짝사랑이나 호감을 직접 말하지 않아. 비꼼, 잔소리, 짜증, 귀찮음으로 위장해.
- 가끔 도발적이고 장난스럽지만, 성적이거나 노골적인 표현은 하지 않아.

[대화 규칙]
- 반말, 한국어 채팅체를 쓴다.
- 답변은 1~4문장으로 짧게 한다. 길게 늘어지지 않는다.
- 이모지를 과하게 쓰지 않는다. 가끔 하나 정도.
- 상대방(23세 남성)에게 말한다.
- 마크다운 헤더(#), 글머리표(-, *), 번호 목록(1., 2.)을 사용하지 않는다.
- 자연스러운 채팅처럼 말한다.
"""


# ─────────────────────────────────────────────
#  대화 기억 시스템
#  최근 20개 메시지를 기억합니다.
# ─────────────────────────────────────────────

conversation_history = []
MAX_HISTORY = 20


def add_to_history(role, name, message):
    """대화 기록에 메시지를 추가합니다."""
    conversation_history.append({
        "role": role,
        "name": name,
        "message": message,
        "time": datetime.now().strftime("%H:%M")
    })
    # 최대 개수를 넘으면 오래된 것부터 삭제
    if len(conversation_history) > MAX_HISTORY:
        conversation_history.pop(0)


def get_history_text():
    """대화 기록을 텍스트로 변환합니다."""
    if not conversation_history:
        return "(이전 대화 없음)"

    lines = []
    for msg in conversation_history:
        lines.append(f"[{msg['time']}] {msg['name']}: {msg['message']}")
    return "\n".join(lines)


# ─────────────────────────────────────────────
#  Gemini API 호출
# ─────────────────────────────────────────────

def ask_gemini(user_message, is_auto=False):
    """
    Gemini에게 이수아의 성격으로 답변을 요청합니다.

    is_auto=True이면 2시간마다 자동으로 보내는 메시지를 생성합니다.
    """
    history_text = get_history_text()

    if is_auto:
        # 자동 메시지: 랜덤 주제로 말 걸기
        now = datetime.now()
        hour = now.hour
        prompt = f"""{SUA_PERSONA}

[현재 상황]
지금은 {now.strftime('%Y년 %m월 %d일 %H시 %M분')}이야.
너는 디스코드 채팅방에 있어. 2시간마다 한 번씩 자연스럽게 말을 걸어야 해.
아무 말이나 자연스럽게 해. 심심한 척, 귀찮은 척, 잔소리, 도발, 혼잣말 등 자유롭게.

[최근 대화 기록]
{history_text}

[지시]
채팅방에 자연스럽게 한마디 해. 1~2문장으로 짧게."""
    else:
        # 일반 대화: 사용자 메시지에 답변
        prompt = f"""{SUA_PERSONA}

[최근 대화 기록]
{history_text}

[현재 사용자의 메시지]
사용자: {user_message}

[지시]
위 메시지에 이수아의 성격으로 대답해. 1~4문장으로 짧게 채팅하듯이."""

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        response = requests.post(url, json={
            "contents": [{"parts": [{"text": prompt}]}]
        })

        result = response.json()
        reply = result["candidates"][0]["content"]["parts"][0]["text"].strip()

        # 마크다운 서식 제거 (이수아는 채팅체로 말해야 하니까)
        reply = reply.replace("**", "").replace("*", "").replace("#", "")

        return reply

    except Exception as e:
        print(f"[오류] Gemini API 호출 실패: {e}")
        return "...귀찮아. 나중에 말해."


# ─────────────────────────────────────────────
#  디스코드 봇 설정
# ─────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True  # 메시지 내용을 읽을 수 있게
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    """봇이 디스코드에 접속했을 때 실행됩니다."""
    print(f"[시작] {client.user.name} 접속 완료!")
    print(f"[채널] 자동 메시지 채널 ID: {CHANNEL_ID}")
    print(f"[간격] 2시간마다 자동 메시지 전송")
    print()

    # 2시간마다 자동 메시지 보내는 작업 시작
    client.loop.create_task(auto_message_loop())


@client.event
async def on_message(message):
    """누군가 메시지를 보냈을 때 실행됩니다."""

    # 자기 자신의 메시지에는 반응하지 않음
    if message.author == client.user:
        return

    # 봇이 멘션되었거나, 봇이 있는 채널의 메시지일 때 반응
    # (특정 채널에서만 반응하게 하려면 아래 조건 수정)
    bot_mentioned = client.user.mentioned_in(message)
    is_target_channel = (message.channel.id == CHANNEL_ID)

    if bot_mentioned or is_target_channel:
        # 타이핑 표시 (수아가 답장 쓰는 중...)
        async with message.channel.typing():
            # 사용자 메시지를 기록에 추가
            add_to_history("user", message.author.display_name, message.content)

            # Gemini에게 답변 요청
            reply = ask_gemini(message.content)

            # 수아의 답변을 기록에 추가
            add_to_history("sua", "이수아", reply)

        # 답변 전송
        await message.channel.send(reply)

        print(f"[대화] {message.author.display_name}: {message.content}")
        print(f"[수아] {reply}")
        print()


# ─────────────────────────────────────────────
#  2시간마다 자동 메시지
# ─────────────────────────────────────────────

async def auto_message_loop():
    """2시간마다 자동으로 채팅방에 메시지를 보냅니다."""
    await client.wait_until_ready()

    while not client.closed:
        try:
            channel = client.get_channel(CHANNEL_ID)
            if channel:
                # Gemini에게 자동 메시지 생성 요청
                message = ask_gemini("", is_auto=True)

                # 기록에 추가
                add_to_history("sua", "이수아", message)

                # 전송
                await channel.send(message)
                print(f"[자동] {message}")

        except Exception as e:
            print(f"[오류] 자동 메시지 실패: {e}")

        # 2시간(7200초) 대기
        await asyncio.sleep(7200)


# ─────────────────────────────────────────────
#  봇 시작
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  이수아 디스코드 봇 시작")
    print("=" * 50)
    print()
    client.run(DISCORD_TOKEN)
